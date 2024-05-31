============
Installation
============

General Options
---------------

At the command line with virtualenvwrapper installed::

    $ mkvirtualenv pywisp
    $ git clone https://github.com/umit-iace/pywisp
    $ python -m pip install .


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

