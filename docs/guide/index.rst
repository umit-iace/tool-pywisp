=====
Guide
=====

To visulize and control a test rig with PyWisp some files are needed that are summarized in a project. Each project
must include the following files:

- main.py: Main file to register all needed :mod:`pywisp.experimentModules`, :mod:`pywisp.connection`, :mod:`pywisp.visualization` and starts the GUI.
- defaults.sreg: The definition of all experiments.
- connection.py: The implementation of all ::mod:`pywisp.connection`.
- visualization.py: The implementation of all :mod:`pywisp.visualization`.
- Files for the :mod:`pywisp.experimentModules`: It is recommended to have one file each module, i.e. `controller`, `testbench`. For detailed information see :ref:`chapter_examples`.

ExperimentModule
----------------

The experiment module class is needed to implement the different parts of the test rig, like trajectory, controller and
testbench handling itself.

3 members must be specified:

- `dataPoints`: Data points, that come from the test rig.
- `publicSettings`: Settings, that can be changed by the user in the GUI.
- `connection`: Connection name, that is required to read and write to the correct connection.

4 functions can be implemented:

- `getStartParams`: Function to handle parameter, that should be set on experiment start.
- `getStopParams`: Function to handle parameter, that should be set on experiment end.
- `getParams`: Function to handle parameter, that should be set on start or during the experiment.
- `handleFrame`: Function to handle frames from test rig and sets the data points to show in the GUI.

For detailed information see the :ref:`chapter_examples` section.

Connection
----------

It is necessary to implement the used connection types, where the class name specify the name used in the GUI and the
default settings. The settings can be changed in the GUI directly. All implementations mus derived from
:class:`~pywisp.visualization.MplVisualizer`. Currently two connection types are available and can implemented exemplary:

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
visualizers based on matplotlib are available. For the implementation the base class
:class:`~pywisp.visualization.MplVisualizer` must be derived and the method
:func:`~pywisp.visualization.MplVisualizer.update` should be implemented. It is recommented to use

.. code-block:: python

    self.canvas.draw_idle()

to update the canvas.

For detailed information see the :ref:`chapter_examples` section.

Remote Widgets
--------------

The `Remote Widgets` give the opportunity to control direct `publicSettings` of
:mod:`pywisp.experimentModules`. It can be added different types of widgets. Currently the following
types are available:

* Push Button
* Slider
* Switch Button

To save the configuration by means of right click the code can be exported and added to the `defaults.sreg`.

Heartbeat
---------

`PyWisp` provides the possibility to send a heartbeat on `ID 1` at bit 1. For the configuration `Config` section of the
`defaults.sreg` must be extended by the setting

.. code-block:: yaml

    Heartbeat: <time in ms>

It can be diabled by set the parameter to zero.

For detailed information see the :ref:`chapter_examples` section.

defaults.sreg
-------------

The `defaults.sreg` constitutes the standard configuration file for `PyWisp`. It uses a `yaml` syntax.
Below a normal configuration with two experiments is presented:

.. code-block:: yaml

    # default experiment file that is loaded when the gui starts up

    - Name: TestSystem

      Test:
        Value1: 11.2
        Value2: 22.1
        Value3: 4
        Value4: 1

    - Name: RunSystem

      SeriesTrajectory:
       StartTime: 5
       StartValue: 28.0
       EndTime: 70
       EndValue: 5.0

      Test:
        Value1: 11.2
        Value2: 22.1
        Value3: 4
        Value4: 1

      Remote:
        PushExample:
          Module: Test
          Parameter: Value1
          valueOn: '99.99'
          widgetType: PushButton
          shortcut: P

      Visu:
        MplExampleVisualizer:

      Config:
        TimerTime: 40
        MovingWindowSize: 5
        MovingWindowEnable: True

In this example `Test` and `SeriesTrajectory` are derived :mod:`pywisp.experimentModules` classes. The settings below
of `Remote` configurates a Push Button, that is connected to ´Value1` of the :mod:`pywisp.experimentModules` class
`Test`. The 'Config' section shows the settings for the plot configuration.

For detailed information see the :ref:`chapter_examples` section.

Plot Configuration
~~~~~~~~~~~~~~~~~~

Additionally the plot and visualization have some configuration parameters. These are:

* TimerTime: Update interval of the visualization/plot data
* MovingWindow: Moving Window of the plot visualization

The can be set by a right click of the plot in the GUI or about the Config menu.
To save the configuration the `defaults.sreg` can be extended by a `Config section` with the keys:

.. code-block:: yaml

    TimerTime:           <time in ms>
    MovingWindowSize:    <time in s>
    MovingWindowEnable:  <True..enable moving window, False..disable moving window>

For detailed information see the :ref:`chapter_examples` section.
