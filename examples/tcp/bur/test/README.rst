==================================
ARsim test for the TCP-B&R example
==================================

``arsim_test.py`` builds the B&R server, starts it in ARsim (or installs it on a PLC) and runs a TCP integration
test against it, without the pyWisp GUI.

.. sphinx-marker

Requirements
^^^^^^^^^^^^

- Windows with B&R Automation Studio 4.4 (``BR.AS.Build.exe``) and PVI (``PVITransfer.exe``)
- ``uv``

Both are searched below ``C:\BrAutomation`` (Automation Studio 4.4 preferred, the project version), pass
``--as-build`` and ``--pvi-transfer`` with the path of the exe if they are elsewhere or the wrong one is used. The test
alone (``--test-only``) runs on any OS against a running server.

Usage
^^^^^

From the repository root:

.. code-block:: powershell

    uv run python examples/tcp/bur/test/arsim_test.py                               # build, ARsim, test, stop ARsim
    uv run python examples/tcp/bur/test/arsim_test.py --skip-build --keep-running   # reuse the last build, keep ARsim
    uv run python examples/tcp/bur/test/arsim_test.py --target-ip 10.0.0.2         # build for and install on the PLC
    uv run python examples/tcp/bur/test/arsim_test.py --test-only --host 10.0.0.2   # test a running server only

``--install-mode ForceInitialInstallation`` reinstalls everything on the PLC if the consistent install fails.
The exit code is the number of failed tests, 1 if build, transfer or start failed, so the script can run in CI.

Steps:

1. ``BR.AS.Build.exe br_server.apj -c minimal -buildMode Rebuild -simulation -buildRUCPackage``
   (without ``-simulation`` for the PLC)
2. ARsim: ``PVITransfer.exe`` creates the ARsim directory from ``Binaries/minimal/.../RUCPackage.zip``
   (``CreateARsimStructure``, PVI 6 calls it ``OfflineCommissioning``), the script starts ``ar000loader.exe`` from it.
   PLC: ``PVITransfer.exe`` installs the RUC package (``Connection`` + ``Transfer``), the PLC restarts.
3. wait until the server listens on port 50007, run the tests
4. stop ARsim (``ar000loader.exe``, ``AR000.exe``), unless ``--keep-running``

Connecting pyWisp afterwards
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

With ``--keep-running`` ARsim keeps running after the test and the client connects to it as usual
(``connection.py`` uses ``127.0.0.1:50007``):

.. code-block:: powershell

    uv run python examples/tcp/bur/test/arsim_test.py --skip-build --keep-running
    cd examples/tcp/bur/client
    uv run python main.py

The server serves one client at a time: while pyWisp is connected the test fails, and right after the test it may
take 1-2 s until the server accepts the next client. To stop ARsim, run the script again (it stops a running ARsim
first) or ``taskkill /F /IM ar000loader.exe /IM AR000.exe``.

Tests
^^^^^

``testIdleStatus``
    the status frame (id 2) arrives while idle, version 1, not running
``testStartSyncStop``
    start after two parameter frames: start counter, frame count and CRC32 match ``pywisp.min.frameCrc``;
    a sync confirms the frames since the last control frame; stop
``testSyncBeforeStart``
    as pyWisp starts: two parameter frames and a sync while idle, the status confirms their count and CRC32 and
    stays idle; the following start reports count 0 and CRC 0
``testDataFrames``
    the ``Test`` parameters (frame 12) come back in frame 10, whose time starts at 0 and grows by 100 ms;
    warns if the server does not run in real time (``Cyclic#4``)
``testMissedHeartbeat``
    without heartbeats the server stops after 1 s and sends id 1 with payload 0, a client that sends heartbeats
    again is kept
``testSilentClientIsDropped``
    the server drops a client that sends nothing for 3 s
``testReconnectAfterAbort``
    after a client vanished during a run, the next client gets an idle status and an aligned stream
