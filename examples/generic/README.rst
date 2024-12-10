Tool-Libs example: Double Pendulum
==================================

This is an example of how a testing rig can be implemented using the tool-libs
framework. The system equations are generated using a sympy c-printer, after
solving the system equations there.

Requirements
------------

* >=Python 3.8
* >=uv 0.5.6-1
* >=Eigen 3.3

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


* Upload

    .. code-block:: bash

        $ make -C build-stm upload


* Upload via OTA

    .. code-block:: bash

        $ make -C build-stm pload_ota UPLOAD=<IP>


* Connect via PyWisp and control the simulation

    .. code-block:: bash

        $ make -C build-sim visu
