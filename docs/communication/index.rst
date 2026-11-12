Communication Diagrams
======================

All diagrams on this page are based on the `generic` example.
The underlying program flow should however only differ slightly on other rigs.

Establishing a connection
-------------------------

A project can register several connections, e.g. USB and WLAN of the same rig. Exactly one of them is
active: it is selected with the radio buttons of the ``Connections`` menu or the drop-down left of the
connect button, only while disconnected. The selection is stored and restored on the next start, the first
registered connection is the default.

``Connect`` in the gui calls :meth:`pywisp.MainGui.connectRig`. The active connection is
established in its reader thread with :meth:`pywisp.connection.Connection.openAsync`, so a rig that
does not answer does not block the gui. Meanwhile the status bar shows ``Connecting ...``. The result
is reported with the ``opened`` signal, once the connection is open the gui is connected.
``Disconnect`` also aborts a connection that is still being established. All experiment modules send
and receive via the active connection.

.. mermaid::
    :caption: Connecting to a serial port

    sequenceDiagram
        box rgba(70, 130, 180, 0.15) PC
            participant User
            participant PyWisp
            participant ReaderThread
            participant SerialPort
        end
        box rgba(60, 179, 113, 0.15) RIG
            participant Runtime
        end

        User->>PyWisp: connectRig()
        PyWisp->>ReaderThread: openAsync()
        PyWisp-->>User: Connecting ...
        ReaderThread->>SerialPort: port.open()
        alt successful case
            SerialPort-->>ReaderThread: OK
            ReaderThread-->>PyWisp: opened(True)
            PyWisp-->>User: Connected!
            ReaderThread->>SerialPort: receive frames
        else failure mode
            SerialPort-->>ReaderThread: Not found
            ReaderThread-->>PyWisp: opened(False)
            PyWisp-->>User: No connection established
        end

.. mermaid::
    :caption: Connecting to a socket

    sequenceDiagram
        box rgba(70, 130, 180, 0.15) PC
            participant User
            participant PyWisp
            participant ReaderThread
            participant Socket
        end
        box rgba(60, 179, 113, 0.15) RIG
            participant Runtime
        end

        User->>PyWisp: connectRig()
        PyWisp->>ReaderThread: openAsync()
        PyWisp-->>User: Connecting ...
        ReaderThread->>Socket: socket.connect()
        alt successful case
            Socket-->>ReaderThread: True
            ReaderThread-->>PyWisp: opened(True)
            PyWisp-->>User: Connected!
            ReaderThread->>Socket: receive frames
        else failure mode
            Socket-->>ReaderThread: Error or timeout
            ReaderThread-->>PyWisp: opened(False)
            PyWisp-->>User: No connection established
        end

Note that all actions occur on the machine that PyWisp is running on, and no
actual data is sent or received over any channel in this step. Only a tcp socket
performs a handshake with the rig. Opening a serial port or connecting a udp socket
succeeds without the rig, so ``Connected!`` does not prove that the rig is running.
A tool-libs rig serves one TCP client at a time. A second client is connected by the operating system as
well, but the rig only reads from it once the first one disconnected, until then it gets no data.

Powering on the rig
-------------------

.. mermaid::
    :caption: Init process of the rig

    sequenceDiagram
        box rgba(60, 179, 113, 0.15) RIG
            participant main as main()
            participant Kernel
            participant Experiment
            participant Model
        end

        Note over Experiment: State = IDLE
        Experiment->>Kernel: register tasks
        main->>Kernel: register communication polling
        main->>Model: m.init()
        Model->>Experiment: register tasks
        Model->>Experiment: register frame handlers
        main->>Kernel: k.run()
        loop every 1 ms
            Kernel->>Kernel: run scheduled tasks
        end


Running an experiment
---------------------

.. mermaid::
    :caption: Running an experiment

    sequenceDiagram
        box rgba(70, 130, 180, 0.15) PC
            participant User
            participant PyWisp
        end
        box rgba(60, 179, 113, 0.15) RIG
            participant Kernel
            participant Experiment
            participant Model
        end

        Note over Experiment: State = IDLE
        Note over PyWisp: runningExperiment = False
        loop every 1 ms
            Kernel->>Model: run IDLE tasks
        end
        Note over User,Model: User starts experiment
        User->>PyWisp: startExperiment()
        PyWisp->>PyWisp: prepareExperiment():<br/>getStartParams(), getParams()
        PyWisp->>Kernel: start parameters and parameters
        Kernel->>Model: Communication handler:<br/>handle frames
        PyWisp->>Kernel: sync (frame ID 1, sync id k)
        Kernel->>Experiment: Communication handler:<br/>handle frame ID 1
        Experiment-->>PyWisp: status (IDLE, sync id k, count, CRC32)
        Note over PyWisp: parameters confirmed,<br/>see the start sequence below
        PyWisp->>PyWisp: runExperiment()
        Note over PyWisp: runningExperiment = True
        PyWisp->>Kernel: start (frame ID 1)
        Kernel->>Experiment: Communication handler:<br/>handle frame ID 1
        Note over Experiment: State = RUN
        Experiment->>Experiment: Event INIT
        Experiment-->>PyWisp: status (RUN, count 0, CRC32 0)
        Kernel->>Model: run INIT tasks
        loop every 1 ms
            Kernel->>Model: run RUN tasks
        end

.. mermaid::
    :caption: Stopping an experiment

    sequenceDiagram
        box rgba(70, 130, 180, 0.15) PC
            participant User
            participant PyWisp
        end
        box rgba(60, 179, 113, 0.15) RIG
            participant Kernel
            participant Experiment
            participant Model
        end

        Note over Experiment: State = RUN
        Kernel->>Model: run RUN tasks
        Note over User,Model: User stops experiment
        User->>PyWisp: stopExperiment()
        Note over PyWisp: runningExperiment = False
        PyWisp->>PyWisp: getStopParams()
        PyWisp->>PyWisp: Append stop frame
        PyWisp->>Kernel: Send everything
        PyWisp->>PyWisp: emit expFinished
        Kernel->>Model: Communication handler:<br/>handle frames
        Kernel->>Experiment: Communication handler:<br/>handle frame ID 1
        Note over Experiment: State = IDLE
        Experiment->>Experiment: Event STOP
        Kernel->>Model: run STOP tasks
        loop every 1 ms
            Kernel->>Model: run IDLE tasks
        end

Note, that again no failure modes are present. Apart from the status frames of rigs that send them (see below),
the rig sends no messages to the pc within this action.

.. _rig_status:

Status of the rig and start confirmation
----------------------------------------

A rig that calls ``e.enableStatus(out)`` of the tool-libs ``Experiment`` sends a status frame with the reserved
id 2 every 250 ms and at every start, also while IDLE. Its payload (little endian):

====== =====================================================
bytes  content
====== =====================================================
0      version, 1
1      state, 0 IDLE, 1 RUN
2      status bits of the project, e.g. "motor driver ready"
3      start counter, incremented by every start command
4-5    number of frames received before that start
6-9    CRC32 over id, length and payload of these frames
10-13  uptime of the rig [ms]
14     id of the last sync command
15-16  number of frames received before that sync
17-20  their CRC32
====== =====================================================

PyWisp takes these frames out before the experiment modules see them. The status bar shows whether the rig responds,
its state and the missing status bits, named by the list ``statusFlags`` of the connection class.
PyWisp computes the same CRC32 over the frames as the rig receives them (:func:`pywisp.min.frameCrc`
over :meth:`pywisp.connection.Connection.rigFrame`, a TCP rig gets every payload padded to ``maxPayload``).

A sync command (:func:`pywisp.min.syncFrame`, control frame with the flags ``SYNC | HEARTBEAT`` and a sync id, see :ref:`control_frame`) lets the rig
confirm parameters: it answers at once with a status frame that carries the number and CRC32 of the frames received
since the last control frame, and resets them.

A start runs in two steps. PyWisp sends the start parameters and the parameters of the experiment, followed by a
sync, while the rig is IDLE. Only once the sync is confirmed, the measurement is created and the start command is
sent, the rig then reports count 0 and CRC 0 with the start. If the sync is not confirmed within 1 s or the rig
received other frames, the experiment is not started and a message box shows why. The start itself is checked as
well: the experiment turns yellow until the rig reports it and green once confirmed, if that is missing, PyWisp starts
once more and stops after a second failure. Rigs with status frames but without sync support (no sync id in the
status) are started right away with a warning in the log, rigs without status frames are not checked at all.

.. mermaid::
    :caption: Start sequence

    sequenceDiagram
        participant User
        participant PyWisp
        participant ConnectionManager
        participant Experiment

        loop every 250 ms
            Experiment-->>ConnectionManager: status (IDLE, start counter n)
        end
        User->>PyWisp: startExperiment()
        PyWisp->>Experiment: start parameters and parameters (prepareExperiment)
        alt rig supports sync
            PyWisp->>ConnectionManager: sync(expected)
            ConnectionManager->>Experiment: sync (frame ID 1, sync id k)
            Experiment-->>ConnectionManager: status (IDLE, sync id k, syncCount, syncCrc)
            Note over ConnectionManager: compare with frameCrc(expected)
            alt count and CRC32 match
                ConnectionManager-->>PyWisp: syncConfirmed(k)
                Note over PyWisp: confirmSettings(lastSent),<br/>new measurement, expectStart([])
                PyWisp->>Experiment: start (frame ID 1)
                Experiment-->>ConnectionManager: status (RUN, start counter n+1, startCount 0, startCrc 0)
                ConnectionManager-->>PyWisp: startConfirmed
                Note over PyWisp: experiment green
            else mismatch or no answer within 1 s
                ConnectionManager-->>PyWisp: syncFailed(k, reason)
                PyWisp-->>User: message box "Start failed"
                Note over PyWisp: no start command, no measurement
            end
        else rig without sync support
            PyWisp-->>User: warning in the log
            Note over PyWisp: new measurement, expectStart(params)
            PyWisp->>Experiment: start (frame ID 1)
            Experiment-->>ConnectionManager: status (RUN, start counter n+1, startCount, startCrc of the params)
            ConnectionManager-->>PyWisp: startConfirmed
        end
        Note over PyWisp,ConnectionManager: startFailed: start once more with a new sync,<br/>stop after the second failure

Parameters sent during the run (remote widgets, *Send parameters*, *Send changed parameter* F8) are followed by a
sync as well. If the confirmation is missing for 1 s or the rig received other frames, PyWisp sends all parameters of
the experiment again, which is correct even if further changes were sent meanwhile. If these are not confirmed
either, the experiment is stopped. To rigs without sync support no sync command is sent.

.. mermaid::
    :caption: Parameter change during a run

    sequenceDiagram
        participant User
        participant PyWisp
        participant ConnectionManager
        participant Experiment

        User->>PyWisp: edit a value
        Note over PyWisp: Rig column red
        User->>PyWisp: F8 or remote widget
        PyWisp->>Experiment: changed parameters (sendChangedParameterExperiment)
        PyWisp->>ConnectionManager: sync(expected)
        ConnectionManager->>Experiment: sync (sync id k)
        Experiment-->>ConnectionManager: status (sync id k, syncCount, syncCrc)
        alt count and CRC32 match
            ConnectionManager-->>PyWisp: syncConfirmed(k)
            Note over PyWisp: confirmSettings: Rig column green,<br/>logParameters(lastTime, changes)
        else mismatch or no answer within 1 s
            ConnectionManager-->>PyWisp: syncFailed(k, reason)
            PyWisp->>Experiment: all parameters (sendParameterExperiment)
            PyWisp->>ConnectionManager: sync(expected)
            ConnectionManager->>Experiment: recovery sync (sync id m)
            alt confirmed
                Experiment-->>ConnectionManager: status (sync id m, syncCount, syncCrc)
                ConnectionManager-->>PyWisp: syncConfirmed(m)
                Note over PyWisp: Rig column green, changes logged
            else failed again
                ConnectionManager-->>PyWisp: syncFailed(m, reason)
                PyWisp->>Experiment: stop (stopExperiment)
            end
        end

The confirmed values are shown in the column *Rig* of the parameter view: green if they equal the value in the
*Value* column, red if the value was edited and not sent or not confirmed yet. Every confirmed value is logged in the
running measurement (:attr:`pywisp.measurement.Measurement.parameters`, ``{'Module.setting': [(time, value), ...]}``,
the values at the start at time 0, later changes at the time of the last received data). The CSV export writes them
as columns ``Module.setting`` between ``time`` and the data points, each value valid until the next change.

.. mermaid::
    :caption: Colour of a cell in the Rig column

    stateDiagram-v2
        state "no colour" as none
        state "red" as red
        state "green" as green
        none : no tracking, disconnected or rig without sync
        red : differs, not sent or not confirmed
        green : confirmed value equals the value

        [*] --> none
        none --> red : status of a rig with sync support (trackRig)
        red --> green : sync confirmed (confirmSettings)
        green --> red : value edited
        red --> red : value edited, sync failed
        green --> red : rig restart (clearRigSettings)
        red --> none : disconnect
        green --> none : disconnect

.. mermaid::
    :caption: Logging and CSV export of the parameters

    flowchart LR
        confirmed["confirmed values<br/>confirmSettings() returns the changes"]
        log["Measurement.logParameters(t, changes)<br/>t = 0 at the start, lastTime later"]
        params["Measurement.parameters<br/>Module.setting: [(t, value), ...]"]
        buffers["Measurement.dataPointBuffers"]
        exporter["Exporter(dataPoints, parameters)"]
        csv["CSV columns: time, Module.setting ..., data points<br/>settings forward filled,<br/>array points expanded to name.1, name.2 ..."]
        confirmed --> log --> params --> exporter
        buffers --> exporter --> csv
