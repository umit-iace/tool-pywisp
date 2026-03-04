Communication Diagrams
======================

All diagrams on this page are based on the `generic` example.
The underlying program flow should however only differ slightly on other rigs.

Establishing a connecting
-------------------------

Depending on the connection type, currently the following happens:

.. uml::
    :caption: Connecting to a serial port

    box "PC" #LightBlue
    participant User
    participant PyWisp
    participant SerialPort
    end box
    box "RIG" #LightGreen
    participant Runtime
    end box

    User -> PyWisp: connect()
    PyWisp -> SerialPort: port.open()
    alt successful case
        PyWisp <-- SerialPort: OK
        User <-- PyWisp: Connection established
    else failure mode
        PyWisp <-- SerialPort: Not found
        User <-- PyWisp: Connection refused
    end

.. uml::
    :caption: Connecting to a socket

    box "PC" #LightBlue
    participant User
    participant PyWisp
    participant Socket
    end box
    box "RIG" #LightGreen
    participant Runtime
    end box

    User -> PyWisp: connect()
    PyWisp -> Socket: socket.connect()
    alt successful case
        PyWisp <-- Socket: True
        User <-- PyWisp: Connection established
    else failure mode
        PyWisp <-- Socket: Error
        User <-- PyWisp: Connection not possible
    end

Note that all actions occur on the machine that PyWisp is running on and no actual
data is sent or received over any channel in this step.

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
