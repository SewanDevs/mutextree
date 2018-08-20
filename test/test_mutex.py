# -*- coding: utf-8 -*-

import redis
import redis_lock
import threading
import time

import pytest
import redislite.patch
from mock import MagicMock

from mutextree import (
    tree_lock,
    TreeLock,
    MutexException,
    NotLockedMutexException,
    RedisLockBackend,
    LocksBackend,
)


def test_LocksBackend():
    lb = LocksBackend()
    lb.get_lock(["A"], 10, "1")
    lb.check_locks_beginning_with("A")
    lb.acquire_lock(None, False, 0)
    lb.release_lock(None)
    lb.refresh_lock(None, 10)


class TestRedisBackEnd(object):
    @staticmethod
    def test_get_lock(monkeypatch):
        backend = RedisLockBackend(None)
        fake_lock_init = MagicMock(return_value=None)
        monkeypatch.setattr("redis_lock.Lock.__init__", fake_lock_init)
        backend.get_lock(["A"], 10, "1")
        assert fake_lock_init.is_called

    @staticmethod
    def test_check_locks_beginning_with():
        redis_client = MagicMock()
        backend = RedisLockBackend(redis_client)
        backend.check_locks_beginning_with("A")
        assert redis_client.keys.is_called

    @staticmethod
    def test_acquire_lock():
        backend = RedisLockBackend(None)
        fake_lock = MagicMock()
        backend.acquire_lock(fake_lock, False, 10)
        assert fake_lock.acquire.is_called

    @staticmethod
    def test_release_lock():
        backend = RedisLockBackend(None)
        fake_lock = MagicMock()
        backend.release_lock(fake_lock)
        assert fake_lock.acquire.is_called

    @staticmethod
    def test_release_lock_exception():
        backend = RedisLockBackend(None)
        fake_lock = MagicMock()
        fake_lock.release = MagicMock(side_effect=redis_lock.NotAcquired)
        with pytest.raises(NotLockedMutexException):
            backend.release_lock(fake_lock)

    @staticmethod
    def test_refresh_lock():
        backend = RedisLockBackend(None)
        fake_lock = MagicMock()
        backend.refresh_lock(fake_lock, 10)
        assert fake_lock.acquire.is_called

    @staticmethod
    def test_refresh_lock_exception():
        backend = RedisLockBackend(None)
        fake_lock = MagicMock()
        fake_lock.extend = MagicMock(side_effect=redis_lock.NotAcquired)
        with pytest.raises(NotLockedMutexException):
            backend.refresh_lock(fake_lock, 10)


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


def test_tree_lock__no_back_end():
    with pytest.raises(ValueError):
        TreeLock(None, ["A"])


def test_tree_lock__empty():
    with pytest.raises(ValueError):
        TreeLock(LocksBackend(), [])


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
    TreeLock(redis_lock_back_end, first_keys, expire=3000, timeout=3000).acquire()
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


def test_release():
    fake_locks_backend = MagicMock()
    tl = TreeLock(locks_backend=fake_locks_backend, nodes_names=["A"])
    tl.real_lock = MagicMock()
    tl.release()
    assert fake_locks_backend.release_lock.called


def test_refresh():
    fake_locks_backend = MagicMock()
    tl = TreeLock(locks_backend=fake_locks_backend, nodes_names=["A"])
    tl.real_lock = MagicMock()
    tl.refresh()
    assert fake_locks_backend.refresh_lock.called


def test_release_not_acquired():
    fake_locks_backend = MagicMock()
    tl = TreeLock(locks_backend=fake_locks_backend, nodes_names=["A"])
    with pytest.raises(NotLockedMutexException):
        tl.release()
    assert not fake_locks_backend.release_lock.called


def test_refresh_not_acquired():
    fake_locks_backend = MagicMock()
    tl = TreeLock(locks_backend=fake_locks_backend, nodes_names=["A"])
    with pytest.raises(NotLockedMutexException):
        tl.refresh()
    assert not fake_locks_backend.refresh_lock.called
