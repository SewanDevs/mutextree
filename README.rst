mutextree
=======
|pipeline_status| |coverage| |black|

To protect tree-like resources:

.. image:: https://gitlab.priv.sewan.fr/sophia/mutex-tree/raw/master/images/mutextree-voc.png

Nodes have to be represented by their fully qualified name.
For instance, the node D is represented by [A, B, D]:

.. image :: https://gitlab.priv.sewan.fr/sophia/mutex-tree/raw/master/images/mutextree-qualified-name.png

The algorithm to lock a node is the following:

1. We lock the parent nodes in order:

.. image :: https://gitlab.priv.sewan.fr/sophia/mutex-tree/raw/master/images/mutextree-step1.png

.. image :: https://gitlab.priv.sewan.fr/sophia/mutex-tree/raw/master/images/mutextree-step2.png

2. Then we check that no child node is already locked:

.. image :: https://gitlab.priv.sewan.fr/sophia/mutex-tree/raw/master/images/mutextree-step3.png

3. We lock the wanted node

.. image :: https://gitlab.priv.sewan.fr/sophia/mutex-tree/raw/master/images/mutextree-step4.png

4. We release all the parent locks that are no longer usefull.

.. image :: https://gitlab.priv.sewan.fr/sophia/mutex-tree/raw/master/images/mutextree-step5.png


Interface targeted to be exactly like threading.Lock_.

.. _threading.Lock : <http://docs.python.org/2/library/threading.html#threading.Lock>`

The mutex tree is actually designed to use redis and python-redis-lock but the locking backend may be changed.


Installation
------------
.. code-block:: console

    $ pip install --trusted-host devpi.priv.sewan.fr --index-url http://devpi.priv.sewan.fr/sophia/prod/ mutextree

Or, if your pipenv is correctly configured:

.. code-block:: console

    $ pipenv install mutextree


Tests
------

Tests should be run under python 2.7 and python 3.6 to tests everything

.. code-block:: console

    $ pip install tox
    $ tox -e py27,py36

Coverage reports will be the merge of the coverage for py27 and py36.


.. |pipeline_status| image:: https://gitlab.priv.sewan.fr/sophia/mutex-tree/badges/master/pipeline.svg
   :target: https://gitlab.priv.sewan.fr/sophia/mutex-tree/pipelines
.. |coverage| image:: https://gitlab.priv.sewan.fr/sophia/mutex-tree/badges/master/coverage.svg
   :target: https://gitlab.priv.sewan.fr/sophia/mutex-tree/commits/master
.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/ambv/black
