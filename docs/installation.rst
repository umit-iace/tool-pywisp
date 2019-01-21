============
Installation
============

General Options
---------------

At the command line with virtualenvwrapper installed::

    $ mkvirtualenv pywisp
    $ git clone https://github.com/umit-iace/pywisp
    $ python setup.py install


For Windows
-----------

PyWisp depends on Qt5.

Qt5 is already included in the most python distributions, to have an easy start
we recommend to use Winpython_ .

.. _Winpython: https://winpython.github.io/

Troubleshooting
---------------

**Missing dependencies (windows)**

If the provided packages on your system are to old, pip may feel obligated to
update them. Since the majority of packages now provide ready to use wheels
for windows on pypi_ this should work automatically.
If for some reason this process fails, you will most certainly find an
appropriate wheel here_ . After downloading just navigate your shell into the
directory and call::

    $ pip install PACKAGE_NAME.whl

to install it.

.. _pypi: https://pypi.python.org/pypi
.. _here: https://www.lfd.uci.edu/~gohlke/pythonlibs/

**PyQT5 Sip**

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
