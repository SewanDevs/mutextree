mutextree
==========
|black|

To protect tree-like resources:

.. image:: https://raw.githubusercontent.com/SewanDevs/mutextree/master-github/images/mutextree-voc.png

Nodes have to be represented by their fully qualified name.
For instance, the node D is represented by [A, B, D]:

.. image :: https://raw.githubusercontent.com/SewanDevs/mutextree/master-github/images/mutextree-qualified-name.png

The algorithm to lock a node is the following:

1. We lock the parent nodes in order:

.. image :: https://raw.githubusercontent.com/SewanDevs/mutextree/master-github/images/mutextree-step1.png

.. image :: https://raw.githubusercontent.com/SewanDevs/mutextree/master-github/images/mutextree-step2.png

2. Then we check that no child node is already locked:

.. image :: https://raw.githubusercontent.com/SewanDevs/mutextree/master-github/images/mutextree-step3.png

3. We lock the wanted node

.. image :: https://raw.githubusercontent.com/SewanDevs/mutextree/master-github/images/mutextree-step4.png

4. We release all the parent locks that are no longer usefull.

.. image :: https://raw.githubusercontent.com/SewanDevs/mutextree/master-github/images/mutextree-step5.png


Interface targeted to be exactly like threading.Lock_.

.. _threading.Lock : <http://docs.python.org/2/library/threading.html#threading.Lock>`

The mutex tree is actually designed to use redis and python-redis-lock but the locking backend may be changed.


Usage
------------

To use mutextree with the redis locks back end, simply instanciate a redis client and create your lock.
The redis client should be strict and decode responses itself.

.. code-block:: python

    import redis
    from mutextree import RedisLockBackend, TreeLock

    redis_client = redis.StrictRedis(decode_responses=True)
    redis_lock_backend = RedisLockBackend(redis_client)
    lock = TreeLock(redis_lock_backend, ["nodeA"], expire=10, timeout=10, id=1)
    try:
        lock.acquire()
        # do things
    finally:
        lock.release()


You can use it as a context manager or a decorator:

.. code-block:: python

    import redis
    from mutextree import RedisLockBackend, TreeLock, tree_lock

    redis_client = redis.StrictRedis(decode_responses=True)
    redis_lock_backend = RedisLockBackend(redis_client)

    with TreeLock(redis_lock_backend, ["nodeA"], expire=10):
        # do things
        pass
        # release will be automatically called

    # Or with a decorator
    @tree_lock(redis_lock_backend, ["nodeA"], expire=10)
    def protected_function():
        # do things
        pass
        # release will be automatically called


Lock has the same basic interface as threading.Lock() with some more methods: acquire, release, refresh.


Tests
------

Tests should be run under python 2.7 and python 3.6 to tests everything

.. code-block:: console

    $ pip install tox
    $ tox -e py27,py36

Coverage reports will be the merge of the coverage for py27 and py36.

.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/ambv/black
