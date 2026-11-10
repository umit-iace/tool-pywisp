=====================================
Visualization for the TCP-B&R example
=====================================

This `pyWisp` example is the client for the B&R server.
The following features are included:

* Remote controls
* Series sent with ``pywisp.utils.packArrayToFrame``

.. sphinx-marker

Usage
^^^^^

Set the ip of the PLC in ``connection.py`` (``127.0.0.1`` for ARsim on the same pc) and run the client from its
folder::

    cd examples/tcp/bur/client
    uv run python main.py

Communication
^^^^^^^^^^^^^

pyWisp's ``TcpConnection`` sends and receives every frame as 1 byte id + 80 bytes payload, shorter payloads are
padded with zeros. All data is little endian. The ids 1 to 5 are reserved for the system frames, the modules
use the ids from 10 on.

``Start`` sends the parameters and a sync while the server is idle, the server confirms count and CRC32 of the
received frames with a status frame, only then pyWisp sends the start (the server reports count 0 and CRC 0 with it).
Without the confirmation the experiment is not started and a message box says why. The column ``Rig`` of the
parameter view shows the confirmed values, red for edited ones until they are sent (``F8``) and confirmed. The
confirmed values are logged with the measurement and exported as CSV columns ``Module.setting`` after ``time``.

The frames:

.. list-table::
    :widths: 10 30 30 15 15
    :header-rows: 1

    * - ID
      - Data type
      - Usage
      - Direction
      - Class
    * - 1
      - 1x byte (+ 1x byte)
      - experiment control (``pywisp.min.Control``): 0 stop, 1 start, 2 heartbeat, 6 + sync id = sync,
        handled by ``TcpIpServer``
      - to server
      -
    * - 1
      - 1x byte (0)
      - missed heartbeat: no heartbeat for 1 s, the experiment was stopped
      - from server
      -
    * - 2
      - 4x byte + unsigned short + 2x unsigned long + byte + unsigned short + unsigned long
      - status (``pywisp.min.RigStatus``): version 1, running, flags, start counter, count and CRC32 of the frames
        before the last start, uptime [ms], sync id, count and CRC32 of the frames before the sync
      - from server
      -
    * - 3-5
      -
      - reserved for future system frames
      -
      -
    * - 10
      - unsigned long + double + float + short + byte + 2x double
      - time [ms] + Value1 + Value2 + Value3 + Value4 + ValueNan + ValueInf
      - from server
      - Test (testbench)
    * - 11
      - unsigned long + double
      - time [ms] + ramp output
      - from server
      - RampTrajectory (trajectory)
    * - 12
      - double + float + short + byte
      - Value1 + Value2 + Value3 + Value4
      - to server
      - Test (testbench)
    * - 13
      - double + unsigned long + double + unsigned long
      - StartValue, StartTime [ms], EndValue, EndTime [ms]
      - to server
      - RampTrajectory (trajectory)
    * - 14
      - unsigned short + 9x double, then 10x double per frame
      - number of values, then all times [ms] and all values of the series (at most 256 values)
      - to server
      - SeriesTrajectory (trajectory)
    * - 15
      - unsigned long + double
      - time [ms] + series output
      - from server
      - SeriesTrajectory (trajectory)
