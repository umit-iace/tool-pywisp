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
data is send or received over any channel in this step.

Powering on the rig
-------------------

.. uml::
    :caption: Init process of the rig

    box "RIG" #LightGreen
    participant Main
    participant Kernel
    participant Experiment
    participant Model
    end box

    Main -> Main: Support.init()
    Main -> Main: Model.init()
    Main -> Kernel: run()
    loop every 1ms
        Kernel -> Kernel: Min.poll()
    end
    note over Experiment: State = IDLE


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

    User -> PyWisp: runExperiment()
    User <-- PyWisp: Experiment is running
    PyWisp -> PyWisp: getStartParams()
    PyWisp -> PyWisp: getParams()
    PyWisp -> PyWisp: Append start frame
    PyWisp -> Kernel: Send everything
    Kernel -> Model: Call handler for each frame
    Kernel -> Experiment: Call handler for ID 1
    note over Experiment: State = RUN
    Kernel <- Experiment: Schedule INIT EVENT
    Kernel -> Model: EVENT INIT
    Model -> Model: reset()
    loop
        Model -> Model: tick()
        Model -> Model: led.toggle()
        Model -> Model: sendData()
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

    == User interacts ==

    User -> PyWisp: stopExperiment()
    User <-- PyWisp: Experiment is stopped
    PyWisp -> PyWisp: getStopParams()
    PyWisp -> PyWisp: Append stop frame
    PyWisp -> Runtime: Send everything
    Kernel -> Model: Call handler for each frame
    Kernel -> Experiment: Call handler for ID 1
    note over Experiment: State = IDLE
    Kernel <- Experiment: Schedule STOP EVENT
    Kernel -> Model: EVENT STOP
    Model -> Model: input.pwm(0)

Note, that again no messages from the rig to the pc are sent within this action and no failure modes are present.