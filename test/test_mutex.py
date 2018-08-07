# -*- coding: utf-8 -*-

import redis
import redis_lock
import threading
import time

import pytest
import redislite.patch

from mutextree import tree_lock, TreeLock, MutexException, RedisLockBackend


@pytest.fixture(autouse=True)
def dont_enforce_strict(monkeypatch):

    old_init = redis_lock.Lock.__init__

    def new_init(*args, **kwargs):
        kwargs["strict"] = False
        return old_init(*args, **kwargs)

    monkeypatch.setattr("redis_lock.Lock.__init__", new_init)


@pytest.fixture(scope="function")
def patch_redis():
    redislite.patch.patch_redis_StrictRedis()
    yield
    redislite.patch.unpatch_redis_StrictRedis()


@pytest.fixture(scope="function")
def redis_lock_back_end(patch_redis):
    redis_client = redis.StrictRedis(decode_responses=True)
    return RedisLockBackend(redis_client)


@pytest.mark.parametrize(
    "keys, result", [([], []), (["A", "B", "C"], ["A;", "A;B;", "A;B;C;"])]
)
def test_generate_cumulative_locks_names(keys, result):
    assert TreeLock._generate_cumulative_locks_names(keys) == result


def test_tree_lock__empty():
    with pytest.raises(ValueError):
        TreeLock(None, [])


@pytest.mark.parametrize(
    "first_keys, second_keys",
    [
        (["A"], ["A"]),
        (["A"], ["A", "B"]),
        (["A", "B"], ["A"]),
        (["A", "B", "C"], ["A"]),
        (["A", "B", "C"], ["A", "B"]),
        (["A"], ["A", "B", "C"]),
        (["A", "B"], ["A", "B", "C"]),
    ],
)
def test_tree_lock__exception(redis_lock_back_end, first_keys, second_keys):
    # hint: set more timeout and more expire if you want to debug ;)
    TreeLock(redis_lock_back_end, first_keys, expire=10, timeout=10).acquire()
    with pytest.raises(MutexException):
        TreeLock(redis_lock_back_end, second_keys).acquire()


@pytest.mark.parametrize(
    "first_keys, second_keys", [(["A"], ["B"]), (["A", "B"], ["A", "C"])]
)
def test_tree_lock(redis_lock_back_end, first_keys, second_keys):
    # hint: set more timeout and more expire if you want to debug ;)
    TreeLock(redis_lock_back_end, first_keys, expire=10, timeout=10).acquire()
    assert TreeLock(redis_lock_back_end, second_keys).acquire()


def test_tree_lock__blocked_thread(monkeypatch, redis_lock_back_end):
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

    def blocked_process(monkeypatch, redis_lock_back_end):
        def lock_with_infinity(*args, **kwargs):
            if getattr(lock_with_infinity, "count", 0) == 0:
                setattr(lock_with_infinity, "count", 1)
                return real_lock_init(*args, **kwargs)
            else:
                set_ready()
                while True:
                    time.sleep(1)

        monkeypatch.setattr("redis_lock.Lock.__init__", lock_with_infinity)
        TreeLock(redis_lock_back_end, ["A", "B"], expire=600, timeout=600).acquire()

    th = threading.Thread(
        target=blocked_process, args=(monkeypatch, redis_lock_back_end)
    )
    th.daemon = True  # To ne killed at the end.
    th.start()
    with pytest.raises(MutexException):
        elapsed_time = 0
        while not is_ready():
            time.sleep(0.1)
            elapsed_time += 0.1
            if elapsed_time > 5:  # seconds
                raise Exception("Too long ! Other thread must be blocked")
        monkeypatch.setattr("redis_lock.Lock.__init__", real_lock_init)
        TreeLock(redis_lock_back_end, ["A", "C"], timeout=0).acquire()


def test_tree_lock__contextmanager(redis_lock_back_end):
    with TreeLock(redis_lock_back_end, ["A"], expire=30):
        with pytest.raises(MutexException):
            TreeLock(redis_lock_back_end, ["A"], timeout=0).acquire()
    assert TreeLock(redis_lock_back_end, ["A"]).acquire()


def test_tree_lock__decorator(redis_lock_back_end):
    @tree_lock(redis_lock_back_end, ["A"], expire=30)
    def locks_too():
        with pytest.raises(MutexException):
            TreeLock(redis_lock_back_end, ["A"], timeout=0).acquire()

    locks_too()
    assert TreeLock(redis_lock_back_end, ["A"]).acquire()
