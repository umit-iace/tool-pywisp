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

.. uml::
    :caption: Connecting to a serial port

    box "PC" #LightBlue
    participant User
    participant PyWisp
    participant ReaderThread
    participant SerialPort
    end box
    box "RIG" #LightGreen
    participant Runtime
    end box

    User -> PyWisp: connectRig()
    PyWisp -> ReaderThread: openAsync()
    User <-- PyWisp: Connecting ...
    ReaderThread -> SerialPort: port.open()
    alt successful case
        ReaderThread <-- SerialPort: OK
        PyWisp <-- ReaderThread: opened(True)
        User <-- PyWisp: Connected!
        ReaderThread -> SerialPort: receive frames
    else failure mode
        ReaderThread <-- SerialPort: Not found
        PyWisp <-- ReaderThread: opened(False)
        User <-- PyWisp: No connection established
    end

.. uml::
    :caption: Connecting to a socket

    box "PC" #LightBlue
    participant User
    participant PyWisp
    participant ReaderThread
    participant Socket
    end box
    box "RIG" #LightGreen
    participant Runtime
    end box

    User -> PyWisp: connectRig()
    PyWisp -> ReaderThread: openAsync()
    User <-- PyWisp: Connecting ...
    ReaderThread -> Socket: socket.connect()
    alt successful case
        ReaderThread <-- Socket: True
        PyWisp <-- ReaderThread: opened(True)
        User <-- PyWisp: Connected!
        ReaderThread -> Socket: receive frames
    else failure mode
        ReaderThread <-- Socket: Error or timeout
        PyWisp <-- ReaderThread: opened(False)
        User <-- PyWisp: No connection established
    end

Note that all actions occur on the machine that PyWisp is running on, and no
actual data is sent or received over any channel in this step. Only a tcp socket
performs a handshake with the rig. Opening a serial port or connecting a udp socket
succeeds without the rig, so ``Connected!`` does not prove that the rig is running.
A tool-libs rig serves one TCP client at a time. A second client is connected by the operating system as
well, but the rig only reads from it once the first one disconnected, until then it gets no data.

Powering on the rig
-------------------

.. uml::
    :caption: Init process of the rig

    box "RIG" #LightGreen
    participant Kernel
    participant Experiment
    participant Model
    end box

    note over Experiment: State = IDLE
    Experiment -> Kernel: register tasks
    == ==
    [-> Kernel: register\ncommunication\npolling
    [-> Model: m.init()
    Model -> Experiment: register tasks
    Model -> Experiment: register frame handlers
    [-> Kernel: k.run()
    loop every 1ms
        Kernel -> Kernel: run scheduled tasks
    end


Running an experiment
---------------------

.. uml::
    :caption: Running an experiment

    box "PC" #LightBlue
    participant User
    participant PyWisp
    end box
    box "RIG" #LightGreen
    participant Kernel
    participant Experiment
    participant Model
    end box

    !pragma teoz true
    note over Experiment: State = IDLE
    &note over PyWisp: runningExperiment = False
    note over Kernel: run scheduled tasks\nevery 1ms
    Kernel -> Model: run IDLE tasks
    == User starts experiment ==
    User -> PyWisp: runExperiment()
    note over PyWisp: runningExperiment = True
    PyWisp -> PyWisp: getStartParams()
    PyWisp -> PyWisp: getParams()
    PyWisp -> PyWisp: Append start frame
    PyWisp -> Kernel: Send everything
    Kernel -> Model: Communication handler:\nhandle frames
    Kernel -> Experiment: Communication handler:\nhandle frame ID 1
    note over Experiment: State = RUN
    Experiment <- Experiment: Event INIT
    Kernel -> Model: run INIT tasks
    loop
    Kernel -> Model: run RUN tasks
    end

.. uml::
    :caption: Stopping an experiment

    box "PC" #LightBlue
    participant User
    participant PyWisp
    end box
    box "RIG" #LightGreen
    participant Kernel
    participant Experiment
    participant Model
    end box

    note over Experiment: State = RUN
    Kernel -> Model: run RUN tasks

    == User stops experiment ==

    User -> PyWisp: stopExperiment()
    note over PyWisp: runningExperiment = False
    PyWisp -> PyWisp: getStopParams()
    PyWisp -> PyWisp: Append stop frame
    PyWisp -> Kernel: Send everything
    [<-- PyWisp: emit expFinished
    Kernel -> Model: Communication handler:\nhandle frames
    Kernel -> Experiment: Communication handler:\nhandle frame ID 1
    note over Experiment: State = IDLE
    Experiment <- Experiment: Event STOP
    Kernel -> Model: run STOP tasks
    loop
    Kernel -> Model: run IDLE tasks
    end

Note, that again no messages from the rig to the pc are sent within this action and no failure modes are present.

.. _rig_status:

Status of the rig and start confirmation
----------------------------------------

A rig that calls ``e.enableStatus(out)`` of the tool-libs ``Experiment`` sends a status frame with the reserved
id 63 every 250 ms and at every start, also while IDLE. Its payload (little endian):

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
For a start, PyWisp computes the same CRC32 over the frames as the rig receives them (:func:`pywisp.min.frameCrc`
over :meth:`pywisp.connection.Connection.rigFrame`, a TCP rig gets every payload padded to ``maxPayload``) and waits up to
1 s for the confirmation. The experiment turns yellow until then and green once confirmed. If the confirmation is
missing or the rig received other frames, PyWisp stops and starts once more, after a second failure the experiment
is stopped. Rigs without status frames are not checked and behave as before.

Parameters sent during the run (remote widgets, *Send parameters*) are followed by a sync command
(:func:`pywisp.min.syncFrame`, control frame with the bits ``0b110`` and a sync id). The rig answers it at once with
a status frame that carries the number and CRC32 of the frames received since the last control frame. If the
confirmation is missing for 1 s or the rig received other frames, PyWisp sends all parameters of the experiment
again, which is correct even if further changes were sent meanwhile. If these are not confirmed either, the experiment
is stopped. Rigs without sync support take the sync command for a heartbeat and are not checked.

.. uml::
    :caption: Confirmed start

    participant PyWisp
    participant Experiment

    loop every 250 ms
    Experiment -> PyWisp: status (IDLE, start counter n)
    end
    PyWisp -> Experiment: parameter frames
    note over Experiment: CRC32 and count\nof the received frames
    PyWisp -> Experiment: start (frame ID 1)
    Experiment -> PyWisp: status (RUN, start counter n+1, count, CRC32)
    note over PyWisp: compare with the sent frames
