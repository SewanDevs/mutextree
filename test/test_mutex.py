# -*- coding: utf-8 -*-

import redis
import redis_lock
import threading
import time

import pytest
import redislite.patch

from mutextree import generate_cumulative_keys, get_tree_lock, MutexException


@pytest.fixture(autouse=True)
def dont_enforce_strict(monkeypatch):

    old_init = redis_lock.Lock.__init__

    def new_init(*args, **kwargs):
        kwargs["strict"] = False
        return old_init(*args, **kwargs)

    monkeypatch.setattr("redis_lock.Lock.__init__", new_init)


@pytest.fixture(autouse=True, scope="function")
def patch_redis():
    redislite.patch.patch_redis_StrictRedis()
    yield
    redislite.patch.unpatch_redis_StrictRedis()


@pytest.mark.parametrize(
    "keys, result", [([], []), (["A", "B", "C"], ["A;", "A;B;", "A;B;C;"])]
)
def test_generate_cumulative_keys(keys, result):
    assert generate_cumulative_keys(keys) == result


def test_get_tree_lock__empty():
    with pytest.raises(ValueError):
        get_tree_lock(None, [])


@pytest.mark.parametrize(
    "first_keys, second_keys",
    [
        (["A"], ["A", "B"]),
        (["A", "B"], ["A"]),
        (["A", "B", "C"], ["A"]),
        (["A", "B", "C"], ["A", "B"]),
        (["A"], ["A", "B", "C"]),
        (["A", "B"], ["A", "B", "C"]),
    ],
)
def test_get_tree_lock__exception(monkeypatch, first_keys, second_keys):
    redis_client = redis.StrictRedis()
    # hint: set more timeout and more expire if you want to debug ;)
    get_tree_lock(redis_client, first_keys, expire=10, timeout=10)
    with pytest.raises(MutexException):
        get_tree_lock(redis_client, second_keys)


@pytest.mark.parametrize("first_keys, second_keys", [(["A", "B"], ["A", "C"])])
def test_get_tree_lock(monkeypatch, first_keys, second_keys):
    redis_client = redis.StrictRedis()
    # hint: set more timeout and more expire if you want to debug ;)
    get_tree_lock(redis_client, first_keys, expire=10, timeout=10)
    assert get_tree_lock(redis_client, second_keys)


def test_get_tree_lock__blocked_thread(monkeypatch):
    redis_client = redis.StrictRedis()
    lock_th = threading.Lock()

    ready = {}

    def is_ready():
        lock_th.acquire()
        is_ready = "ready" in ready
        lock_th.release()
        return is_ready

    def set_ready():
        lock_th.acquire()
        ready["ready"] = True
        lock_th.release()

    real_lock_init = redis_lock.Lock.__init__

    def blocked_process(monkeypatch, redis_client):
        def lock_with_infinity(*args, **kwargs):
            if getattr(lock_with_infinity, "count", 0) == 0:
                setattr(lock_with_infinity, "count", 1)
                return real_lock_init(*args, **kwargs)
            else:
                set_ready()
                while True:
                    time.sleep(1)

        monkeypatch.setattr("redis_lock.Lock.__init__", lock_with_infinity)
        get_tree_lock(redis_client, ["A", "B"], expire=600, timeout=600)

    th = threading.Thread(target=blocked_process, args=(monkeypatch, redis_client))
    th.daemon = True  # To ne killed at the end.
    th.start()
    with pytest.raises(MutexException):
        while not is_ready():
            time.sleep(0.1)
        monkeypatch.setattr("redis_lock.Lock.__init__", real_lock_init)
        get_tree_lock(redis_client, ["A", "C"], timeout=0)
