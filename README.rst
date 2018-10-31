=====================================================
PyWisp - Weird visualisation of test bench prototypes
=====================================================


Install
-------

For standard use:

.. code-block:: bash

    $ git clone pywisp
    $ cd pywisp/
    $ python setup.py install

For development use:

.. code-block:: bash

    $ virtualenv pywisp
    $ git pywisp
    $ cd pywisp/
    $ python setup.py develop

Problems
--------

If the application doesn't start and returns a PyQt error like

.. code-block:: bash

    user@machine % python main.py
    Traceback (most recent call last):
        File "main.py", line 5, in <module>
            from PyQt5.QtWidgets import QApplication
    ModuleNotFoundError: No module named 'PyQt5.sip'
    
then PyQt5 and PyQt5.sip must be uninstalled and PyQt5 must be reinstalled

.. code-block:: bash

    $ pip uninstall pyqt5-sip
    $ pip uninstall pyqt5
    $ pip install pyqt5
    
    
