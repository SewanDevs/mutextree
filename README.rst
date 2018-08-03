Mutex-Tree
=======
|pipeline_status| |coverage| |black|

To protect tree-like resources

Installation
------------
.. code-block:: console


    $ pip install --trusted-host devpi.priv.sewan.fr --index-url http://devpi.priv.sewan.fr/sophia/prod/ mutex-tree

Or, if your pipenv is correctly configured:

.. code-block:: console

    $ pipenv install mutex-tree


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
