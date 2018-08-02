# -*- coding: utf-8 -*-

import pytest
import redislite.patch

import redis
import redis_lock
from threading import Thread

from mutex import generate_cumulative_keys, get_tree_lock, MutexException


@pytest.fixture(autouse=True)
def dont_enforce_strict(monkeypatch):

    old_init = redis_lock.Lock.__init__
    def new_init(*args, **kwargs):
        kwargs["strict"] = False
        return old_init(*args, **kwargs)

    monkeypatch.setattr("redis_lock.Lock.__init__", new_init)


@pytest.fixture(autouse=True)
def patch_redis():
    redislite.patch.patch_redis_StrictRedis()
    yield
    redislite.patch.unpatch_redis_StrictRedis()


@pytest.mark.parametrize(
    "keys, result", [([], []), (["A", "B", "C"], ["A;", "A;B;", "A;B;C;"])]
)
def test_generate_cumulative_keys(keys, result):
    assert generate_cumulative_keys(keys) == result


def test_get_tree_lock():
    with pytest.raises(ValueError):
        get_tree_lock(None, [])


def test_get_tree_lock__root_locked(monkeypatch):
    redis_client = redis.StrictRedis()
    lock = get_tree_lock(redis_client, ["A"], expire=600, timeout=600)
    with pytest.raises(MutexException):
        lock2 = get_tree_lock(redis_client, ["A", "B"])


def test_get_tree_lock__leave_locked(monkeypatch):
    redis_client = redis.StrictRedis()
    lock = get_tree_lock(redis_client, ["A", "B"], expire=600, timeout=600)
    with pytest.raises(MutexException):
        lock2 = get_tree_lock(redis_client, ["A"])


def test_get_tree_lock__blocked_thread(monkeypatch):
    pass
    # redis_client = StrictRedis()
    # monkeypatch.
