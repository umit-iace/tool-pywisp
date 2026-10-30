Communication Diagrams
======================

All diagrams on this page are based on the `generic` example.
The underlying program flow should however only differ slightly on other rigs.

Establishing a connection
-------------------------

``Connect`` in the gui calls :meth:`pywisp.MainGui.connectRig`. Every registered connection is
established in its reader thread with :meth:`pywisp.connection.Connection.openAsync`, so a rig that
does not answer does not block the gui. Meanwhile the status bar shows ``Connecting ...``. The result
is reported with the ``opened`` signal, once all connections are open the gui is connected. If one of
them fails, all others are closed again. ``Disconnect`` also aborts connections that are still being
established.

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
