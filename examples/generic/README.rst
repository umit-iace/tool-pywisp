Tool-Libs example: Double Pendulum
==================================

.. sphinx-marker

This is an example of how a testing rig can be implemented using the tool-libs
framework. The system equations are generated using a sympy c-printer, after
solving the system equations there.

The tool-libs version is the one pywisp requires, ``TOOL_LIBS_VERSION`` in
``pywisp/__init__.py``. ``tests/test_example_generic.py`` builds the simulation with it
and runs an experiment.

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

  The visu registers two connections, ``Udp`` (127.0.0.1:45670, the default) and ``Tcp`` (127.0.0.1:45671).
  Select one in the ``Connections`` menu or the drop-down of the toolbar before connecting.
  The simulation serves both at the same time (MIN frames over UDP, frames padded to 80 bytes payload
  over TCP, one TCP client at a time) and answers over the one that received the last frame.
  TCP needs a tool-libs version with the ``TCP`` transport.

* Start, parameters and export

  ``Start`` sends the parameters followed by a sync, the simulation confirms them and only then the start command is
  sent. If they are not confirmed, the experiment is not started and a message box says why. The column ``Rig`` of
  the parameter view shows the values the simulation confirmed: red after editing a value, green again once it is
  sent with ``F8`` (*Send changed parameter*) and confirmed. The confirmed values are logged with the measurement, the
  CSV export writes them as columns ``Module.setting`` (e.g. ``DoublePendulum.Config``) after ``time``.
  ``tests/test_example_generic.py`` checks this over UDP and TCP.

* Log messages of the rig

  ``Model::init`` (``inc/model.h``) enables the log frames with
  ``e.enableLog(out, Logger::bit(Logger::INFO) | Logger::bit(Logger::WARN) | Logger::bit(Logger::ERROR))``:
  messages of ``k.log`` and of the experiment (e.g. ``started``) with a level in the mask are also sent to PyWisp,
  which shows them in the log window under the name ``Rig`` with their level, e.g. after setting the trajectory type
  ``12:00:00 - Rig - INFO - trajectory type set to LIN``. The messages are sent only when they are logged, the
  cyclic ``k.log.print`` of the simulation (level ``NONE``, not in the mask) stays on the console.


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
    $ pacman -S python3 uv eigen cmake arm-none-eabi-gcc git make gcc libgl qt6-base

Switch to correct folder and install enviroment::

    $ cd tool-pywisp/examples/generic
    $ uv venv
    $ uv sync

If you are using `WSL` Version 1, you need to install an `X11` window server, for example `VcXsrv <https://vcxsrv.com/>`
In some cases, it is necessary to set the display variable with::

    $ export DISPLAY=:0
