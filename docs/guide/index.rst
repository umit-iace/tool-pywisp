=====
Guide
=====

To visulize and control a test rig with pywisp a project is needed. Each project must include the following files:

- main.py: Main file to register all needed modules and start the visualization GUI.
- defaults.sreg: The definition of all experiments, that would be done.
- connection.py: The implementation of all connection, that are necessary for the test rig.
- visualization.py: All implementations of all visualizer.
- Files for the experiment modules: It is recommended to have one file each module, i.e. controller, testbench. For detailed information see the example section.

ExperimentModule
----------------

The experiment module class is needed to implement the different parts of the test rig, like trajectory, controller and
testbench handling itself.

2 members must be specified:

- `dataPoints`: Data points, that come from the test rig.
- `publicSettings`: Settings, that can be changed by the user in the GUI.
- `connection`: Connection name, that is required to read and write to the correct connection.

4 functions must be implemented:

- `getStartParams`: Function to handle parameter, that should be set on experiment start.
- `getStoparams`: Function to handle parameter, that should be set on experiment end.
- `getParams`: Function to handle parameter, that should be set on start or during the experiment.
- `handleFrame`: Function to handle frames from test rig and sets the data points to show in the GUI.

For detailed information see the example section.

Connection
----------

It is necessary to implement the used connection types, where the class name specify the name used in the GUI and the
default settings. The settings can be changed in the GUI directly. All implementations mus derived from `py:MplVisualizer`.
Currently two connection types are available and can implemented exemplary:

- Serial connection:

.. code-block:: python

    class ConnName(SerialConnection):
        settings = OrderedDict([("port", '/dev/uart0'),
                                ("baud", 115200),
                                ])

        def __init__(self):
            SerialConnection.__init__(self,
                                      self.settings['port'],
                                      self.settings['baud'])


- Tcp connection

.. code-block:: python

    class ConnName(TcpConnection):
        settings = OrderedDict([("ip", '192.168.1.1'),
                                ])

        def __init__(self):
            TcpConnection.__init__(self,
                                   self.settings['ip'])

Visualizer
----------

It is possible to have different visualizers registered. They can be selected in GUI at runtime. Currently only
visualizers based on matplotlib are available. For the implementation the base class `py:MplVisualizer` must be
derived and the method `update` should be implemented.

For detailed information see the example section.
