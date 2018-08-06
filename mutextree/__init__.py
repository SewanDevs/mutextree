# -*- coding: utf-8 -*-

import redis_lock
from decorator import decorator


class MutexException(Exception):
    pass


class LocksBackend(object):
    """ Abstract base class for locks backends. """

    def get_lock(self, lock_name, expire, id):
        """ Return a lock with the same interface as threading.Lock.
        Args:
            lock_name (str): name of the lock.
            expire (int): expiring time of the lock. The lock will be released after this duration.
            id (str): id of the lock holder.
        Returns:
            Object with acquire() and release() method (same interface as threading.Lock)
        """
        pass

    def check_locks_beginning_with(self, name):
        """ Verify that all locks begining with name are available.
        No guaranties that they will all still be available when getting them.
        Args:
            name (str): a beginning of locks names.
        Returns:
            list of locks names beginning with name.
        """
        pass


class RedisLockBackend(LocksBackend):
    def __init__(self, redis_client):
        self.redis_client = redis_client

    def get_lock(self, lock_name, expire, id):
        return redis_lock.Lock(self.redis_client, lock_name, expire=expire, id=id)

    def check_locks_beginning_with(self, name):
        found_keys = self.redis_client.keys("lock:" + name + "*")
        # remove "lock:"
        return [found_key.replace("lock:", "") for found_key in found_keys]


@decorator
def tree_lock(func, locks_backend=None, nodes_names=None, expire=30, id=None, timeout=0, *args, **kwargs):
    """ Decorator to lock a resource in a tree like hierarchy. Lock is acquired before the decorated function
    and released after, the function being successfull or not.
    Preserve method signature.
    Args:
        func: decorated function.
        locks_backend (LocksBackend): a locks backend.
        nodes_names (str list): a list of the nodes names representing the resource in the tree.
        expire (int): expiring time of the lock. The lock will be released after this duration
        id (str): id of the lock holder.
        timeout (int): time out of the acquering of the lock.
            Non bloking if timeout is null.
        *args, **kwargs: args for the decorated function
    """
    with TreeLock(locks_backend, nodes_names, expire, id, timeout):
        return func(*args, **kwargs)


class TreeLock(object):
    """ Acquire a lock for a resource in a tree-like hierarchy represented by the names of the nodes.
    Checks that no resource above or under in the tree is already locked.
    Interface targeted to be exactly like `threading.Lock <http://docs.python.org/2/library/threading.html#threading.Lock>`
    """

    def __init__(self, locks_backend, nodes_names, expire=30, id=None, timeout=0):
        """ Initialise the tree lock, nothing is done during initialisation
        Args:
            locks_backend (LocksBackend): a locks backend.
            nodes_names (str list): a list of the nodes names representing the resource in the tree.
            expire (int): expiring time of the lock (see redis_lock).
            id (str): id of the process (see redis_lock).
            timeout (int): time out of the acquering of the lock (see redis_lock).
                Non bloking if timeout is null.
        """
        if not locks_backend:
            raise ValueError("locks_backend is mandatory")
        self.locks_backend = locks_backend
        if not nodes_names:
            raise ValueError("nodes_names cannot be empty")
        self.nodes_names = nodes_names
        self.expire = expire
        self.id = id
        self.timeout = timeout
        self.real_lock = None

    def acquire(self):
        """ Acquire the lock. All the checks are done: no resource above or under in the tree is already locked.
        Returns:
            self
        Raises:
            MutexException in case of error.
        """
        cumulative_locks_names = self._generate_cumulative_locks_names(self.nodes_names)
        parent_locks_names, lock_name = cumulative_locks_names[:-1], cumulative_locks_names[-1]
        parent_locks = self._acquire_parent_locks(parent_locks_names)
        try:
            # Maybe we could wait a bit to see if the child lock is released and take some time from the timeout
            self._check_no_childs_lock(lock_name)
            # Maybe we could compute the already elapsed time to subtract from timeout
            # It would reduce the chances that we don't have the parent locks anymore when have the acquire this
            # one.
            self.real_lock = self._acquire_real_lock(lock_name)
            return self
        finally:
            for lock in parent_locks:
                lock.release()

    def release(self):
        self.real_lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    @staticmethod
    def _generate_cumulative_locks_names(nodes_names):
        """ Returns the cumulative locks names from a list of nodes names. Cumulative locks names are all the
        names formed by concatenation of node names in order: for [A,B,C] we will have A, AB and ABC.
        Args:
            nodes_names (str list): list of nodes names
        Returns
            str list: list of locks names.
        """
        cumulative_names = nodes_names[:1]
        for node_name in nodes_names[1:]:
            cumulative_names.append(cumulative_names[-1] + ";" + node_name)
        cumulative_names = [name + ";" for name in cumulative_names]
        return cumulative_names

    def _acquire_parent_locks(self, parent_locks_names):
        """ Acquire in order the locks of all parents of the node. The locks will be acquired for at least
        lock_timeout so that there are still locked when the real lock is acquired.
        Locks are automatically released if there is an exception.
        Args:
            parent_locks_names (str list): list of lock names to acquire in order
        Returns:
            list of all parent locks. They are already acquired.
        Raises:
            MutexException if any lock is not available.
        """
        try:
            parent_locks = []
            for key in parent_locks_names:
                # We must keep all the locks above the real one until we acquire it.
                # So, we must keep the locks for at least timeout seconds.
                expire_time = self.timeout + 5
                # Maybe we could wait a bit before raising exception to see if lock is released and take some
                # time from the timeout.
                lock = self.locks_backend.get_lock(key, expire=expire_time, id=self.id)
                if lock.acquire(blocking=False):
                    parent_locks.append(lock)
                else:
                    raise MutexException(
                        "Lock not available because '{}' is locked".format(key)
                    )
            return parent_locks
        except Exception:
            for lock in parent_locks:
                lock.release()
            raise

    def _check_no_childs_lock(self, lock_name):
        """ Checks that all child locks are available.
        Args:
            lock_name (str): name of the real lock
        Raises:
            MutexException if any child lock is not available
        """
        found_keys = self.locks_backend.check_locks_beginning_with(lock_name)
        if found_keys:
            raise MutexException(
                "Lock not available because {} are locked".format(found_keys)
            )

    def _acquire_real_lock(self, lock_name):
        """ Acquire the real lock. Non bloking if timeout is null.
        Args:
            lock_name (str): lock name.
        """
        real_lock = self.locks_backend.get_lock(lock_name, expire=self.expire, id=self.id)
        blocking = self.timeout != 0
        timeout = self.timeout or None
        real_lock.acquire(blocking=blocking, timeout=timeout)
        return real_lock
