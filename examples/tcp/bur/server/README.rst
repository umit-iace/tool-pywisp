==============================
Server for the TCP-B&R example
==============================

.. sphinx-marker

Requirements
^^^^^^^^^^^^

For the usage of the B&R code the following programs are needed:

- B&R Automation Studio 4.4 (the project is saved with 4.4.6.71 SP)

Usage
^^^^^

Open ``br_server.apj`` in Automation Studio and build it. Start the simulation (ARsim) or a PLC and transfer the
project to it. The server listens on TCP port 50007, the ip is set in the ``connection.py`` of the client
(``127.0.0.1`` for ARsim on the same pc).

Structure
^^^^^^^^^

Both tasks run in ``Cyclic#4`` (100 ms), ``ControlLoop`` before ``TcpIpServer``:

- ``ControlLoop`` computes the ramp (``trajData.dOutput``) and interpolates the received series
  (``trajData.dSeriesOutput``) at ``benchData.lTime`` [ms].
- ``TcpIpServer`` runs the ``TcpIpServer`` library, which accepts one client at a time and handles the experiment
  control of pyWisp (start, stop, heartbeat, sync, status frame), and passes all other frames to ``Transport``.
  While the experiment runs it sends the data frames every cycle and counts ``benchData.lTime`` up by 100 ms,
  a start resets it to 0.
- ``Transport`` packs and unpacks the data frames, ``Frame`` packs little endian, as ``struct`` format ``<``.

The experiment control works like the ``Experiment`` of tool-libs:

- Without heartbeat for 1 s the experiment stops and the server sends a control frame with payload 0 (missed
  heartbeat), pyWisp then disconnects. A client that still holds the connection 1 s later is dropped.
  ``HeartbeatTime`` in ``default.sreg`` must be below 1000 ms.
- The status frame (``pywisp.min.RigStatus``) is sent every 250 ms (with a 100 ms cycle every 300 ms), at a start
  and at a sync. It carries the number and the CRC32 of the frames received before the start or sync, so pyWisp
  can check that the parameters arrived.
