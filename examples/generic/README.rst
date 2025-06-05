Tool-Libs example: Double Pendulum
==================================

.. sphinx-marker

This is an example of how a testing rig can be implemented using the tool-libs
framework. The system equations are generated using a sympy c-printer, after
solving the system equations there.

Requirements
------------

* >=Python 3.10
* >=uv 0.5.6-1
* >=Eigen 3.3
* >=cmake 3.24
* >=arm-none-eabi-* 14.2.0

Simulation
----------

* Configure

    .. code-block:: bash

        $ cmake -S . -B build-sim -D SIM=1

* Build and run the simulation

    .. code-block:: bash

        $ make -C build-sim run

    or

    .. code-block:: bash

        $ cmake --build build-sim --target run


* Connect via PyWisp and control the simulation

    .. code-block:: bash

        $ make -C build-sim visu


STM
---

* Configure

    .. code-block:: bash

        $ cmake -S . -B build-stm -D SIM=0


* Build the STM code

    .. code-block:: bash

        $ make -C build-stm stm


* Upload via ST-Link programmer

    .. code-block:: bash

        $ make -C build-stm upload


* Upload via OTA

    .. code-block:: bash

        $ make -C build-stm upload_ota UPLOAD=<IP>


* Connect via PyWisp and control the simulation

    .. code-block:: bash

        $ make -C build-sim visu

Windows
-------

Using of `WSL` (Windows-Subsystem for Linux) at the command line::


    $ wsl -- install archlinux

After installation is done, you can switch in the `WSL` enviroment with::

    $ wsl

and install the following packages::

    $ pacman -Syu
    $ pacman -S python3 uv eigen cmake arm-none-eabi-gcc git make gcc libgl qt5-base

Switch to correct folder and install enviroment::

    $ cd tool-pywisp/examples/generic
    $ uv venv
    $ uv sync

If you are using `WSL` Version 1, you need to install an `X11` window server, for example `VcXsrv <https://vcxsrv.com/>`
In some cases, it is necessary to set the display variable with::

    $ export DISPLAY=:0
