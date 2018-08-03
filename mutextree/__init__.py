# -*- coding: utf-8 -*-

import redis_lock


class MutexException(Exception):
    pass


def get_tree_lock(redis_client, keys, expire=30, id=None, timeout=0):
    """ Acquire a lock for a tree-like resource represented by keys. Checks that no resource above or under
    in the tree is already locked.

    Args:
        redis_client (redis.StrictRedis): a redis client
        keys (str list): the keys representing the resource in the tree.
        expire (int): expiring time (see redis_lock)
        id (str): id of the process (see redis_lock)

    Returns:
        a redis_lock.Lock object already acquired.
    """

    if not keys:
        raise ValueError("keys cannot be empty")

    locks_to_release = []
    cumulative_keys = generate_cumulative_keys(keys)
    try:
        for key in cumulative_keys[:-1]:
            # We must keep all the locks above the real one until we acquire it.
            # So, we must keep the locks for at least timeout seconds.
            expire_time = timeout + 5
            lock = redis_lock.Lock(redis_client, key, expire=expire_time)
            if lock.acquire(blocking=False):
                locks_to_release.append(lock)
            else:
                raise MutexException(
                    "Lock not available because '{}' is locked".format(key)
                )

        real_mutex_key = cumulative_keys[-1]
        found_keys = redis_client.keys("lock:" + real_mutex_key + "*")
        if found_keys:
            raise MutexException(
                "Lock not available because {} are locked".format(found_keys)
            )

        real_lock = redis_lock.Lock(redis_client, real_mutex_key, expire, id)
        blocking = timeout != 0
        timeout = timeout or None
        real_lock.acquire(blocking=blocking, timeout=timeout)
        return real_lock
    finally:
        for lock in locks_to_release:
            lock.release()


def generate_cumulative_keys(keys):
    cumulative_keys = keys[:1]
    for key in keys[1:]:
        cumulative_keys.append(cumulative_keys[-1] + ";" + key)
    cumulative_keys = [cum_key + ";" for cum_key in cumulative_keys]
    return cumulative_keys
