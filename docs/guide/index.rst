=====
Guide
=====

This guide shows how to configure the remote part for a test rig.
Most of the time this is some kind of PC that is connected to the rig and can be used
to start and stop experiments as well as to collect and visualize measurements.
Regarding the code on the test rig itself, please refer to the `tool-libs
<https://github.com/umit-iace/tool-libs>`_ documentation.

To visualize and control a test rig with PyWisp some files are needed that are summarized in a project. Each project
must include the following files:

- ``connection.py``: The implementation of all :mod:`pywisp.connection`.
- Files for the :mod:`pywisp.experimentModules`: It is recommended to have one file for each module, i.e. `controller`,
  `testbench`. For detailed information see :ref:`chapter_examples`.
- ``visualization.py``: The implementation of all :mod:`pywisp.visualization`.
- ``defaults.sreg``: The definition of all experiments.
- ``main.py``: Main file to register all needed :mod:`pywisp.experimentModules`, :mod:`pywisp.connection`,
  :mod:`pywisp.visualization` and starts the GUI.

PyWisp is based on PyQt6. Projects written for former versions using PyQt5 have to be adapted, since both cannot be
used in the same program:

- Import Qt classes from ``PyQt6`` instead of ``PyQt5``, e.g. ``from PyQt6.QtWidgets import QApplication``.
- Call ``app.exec()`` instead of ``app.exec_()``.
- Enums have to be fully qualified, e.g. ``Qt.AlignmentFlag.AlignLeft`` instead of ``Qt.AlignLeft``.
- Visualizers using matplotlib directly import the canvas from ``matplotlib.backends.backend_qtagg``.

Connection
----------

Before anything can happen, it is necessary to implement a communication channel to the rig.
PyWisp already comes with generic connection types like
:class:`pywisp.connection.SerialConnection` for communication over serial ports like USB as well
:class:`pywisp.connection.TcpConnection` or :class:`pywisp.connection.UdpConnection` for Socket based communication.

To implement your specific connection, just derive from
:class:`pywisp.connection.Connection` or one of the classes mentioned above.
Its ``_connect`` method is called in the reader thread of the connection, so it may block, e.g. until a
timeout, but must not access the gui. Scripts without a gui can use the blocking
:meth:`pywisp.connection.Connection.open` instead of :meth:`pywisp.connection.Connection.openAsync`.
The actual settings such as ports and baud rate can also be changed in the GUI later on.
A simple UDP based setup could look like this:

.. literalinclude:: ../../examples/generic/visu/connection.py
   :language: python
   :lines: 5-12

ExperimentModule
----------------

The experiment module class is needed to implement the different parts of the test rig, like trajectory, controller and
testbench handling itself. To implement your functionality, derive from it and then implement the following:

First, declare the following member variables:

- :attr:`connection`:``str`` -- The name of the connection class (derived from :class:`pywisp.connection.Connection`) that shall be used to
  communicate with the test rig.
- :attr:`publicSettings`:``dict`` -- Settings for the module that will be exposed in the GUI and can be changed by the user (e.g.
  controller gains).
- :attr:`dataPoints`:``list[str]`` -- Labels of the measurements that come from the test rig to be used for plots.

Then, implement the following methods that are invoked when data is sent *from* PyWisp *to* the test rig:

- :meth:`getStartParams`: return parameters that should be set on experiment start.
- :meth:`getStopParams`: return parameters that should be set on experiment end.
- :meth:`getParams`: return parameters that should be set after start and during the experiment.

All of these 3 functions must return a list of dicts each representing a data frame to be sent to the rig.
They receive one positional argument, which is a list of the currently set :attr:`publicSettings` of the module.
For more information on data frames, please refer to :ref:`communication_layer`. To just send one bool value, an implementation
could look like

.. literalinclude:: ../../examples/generic/visu/testbench.py
   :language: python
   :lines: 24-35

Finally, the measurement data from the rig must be processed, to do so implement :meth:`handleFrame`
to handle frames from test rig such that it can be shown in the GUI. It returns ``None`` for frames that are not
meant for the module.

All four methods are optional, the default implementations send nothing and ignore all frames.

PyWisp creates an instance of the module when an experiment using it is applied and keeps it until another
experiment is applied. Hence, state like a cached trajectory can be stored in attributes, initialize them in
``__init__`` after calling ``super().__init__()``. The member variables listed above have to remain class attributes.

The current values of the settings are available by name in :attr:`settings`, e.g. ``self.settings['gain']``. They hold
the values of the applied experiment and are updated right before one of the three parameter methods is called, so
:meth:`handleFrame` always sees the values that have been sent to the rig last.

For actual implementations please refer to the :ref:`chapter_examples` section.

Visualizer
----------

It is possible to have different visualizers registered.
They can be selected in GUI at runtime.
Currently, only visualizers based on matplotlib are available.
To visualize your rig, derive from
:class:`~pywisp.visualization.MplVisualizer` and implement
:func:`~pywisp.visualization.MplVisualizer.update`.
To update the canvas, it is recommended to use

.. code-block:: python

    self.canvas.draw_idle()

The GUI offers light and dark themes (``View`` → ``Theme``), the button right of the visualizer
selection switches between the last used light and dark theme. The axes of a
:class:`~pywisp.visualization.MplVisualizer` follow the theme, visualizers drawing further elements in theme
colors override :func:`~pywisp.visualization.Visualizer.updateTheme`, it is called after loading the
visualizer and after every switch.

For detailed information see the :ref:`chapter_examples` section.

Remote Widgets
--------------

The `Remote Widgets` give the opportunity to change the :attr:`publicSettings` of the
:mod:`pywisp.experimentModules` without editing them by hand in the tree view.

Currently, the following types are available:

* Push Button
* Slider
* Switch

To use the widgets, either right click in the ``Remote`` dock container in the GUI,
select ``Add widget`` and follow the wizard, or manually define them under the ``Remote`` part
of your experiment configuration (an ``.sreg`` as explained below) like so:

.. literalinclude:: ../../examples/tcp/bur/client/default.sreg
   :language: yaml
   :lines: 23-45

Widgets can be moved by dragging them with the right mouse button. Their place is stored in the optional
``position`` entry, given as ``[x, y]`` in pixels. Widgets without a position are arranged in two columns.

Widgets created, changed, moved or removed in the GUI are not saved automatically. Use ``File`` →
``Save experiments`` (``Ctrl+S``) or ``Save experiments`` in the context menu of the ``Remote`` dock to write all
experiments back to the loaded ``.sreg`` file, ``Save experiments as ...`` writes them to a new file. Experiments that
could not be loaded are written unchanged. Since comments and formatting of the file are lost, the original file is
kept as ``.sreg.bak`` before it is overwritten for the first time. To only export the widgets of the current
experiment, ``Copy remote source`` in the context menu copies them to the clipboard.

Heartbeat
---------

`PyWisp` provides the possibility to automatically stop a rig if the connection
is interrupted.
To use this feature, the ``Config`` section of the ``.sreg`` file must include
the setting

.. code-block:: yaml

    HeartbeatTime: 100  # send a heartbeat every 100ms

It can be disabled by setting the parameter to zero or omitting the entry.
Note that the embedded code on the rig itself also has to be configured to expect such a packet.
Refer to the `tool-libs <https://github.com/umit-iace/tool-libs>`_ documentation for details.

Logging
~~~~~~~

Importing pywisp does not touch the logging configuration. When the :class:`pywisp.MainGui` is created, it sets up
console output with level ``INFO``, unless the application has configured logging before, e.g. with
``logging.basicConfig()``. Scripts that do not create the GUI can call :func:`pywisp.setupLogging` to get the same
output.

Plot Configuration
~~~~~~~~~~~~~~~~~~

Additionally, the plot and visualization have some configuration parameters. These are:

* TimerTime: Update interval of the visualization/plot data
* MovingWindow: Moving Window of the plot visualization

They can be set interactively by right-clicking the plot in the GUI and in the Config menu.
To save the configuration the ``defaults.sreg`` ``Config`` section can be extended with the keys:

.. code-block:: yaml

    TimerTime:           <time in ms>
    MovingWindowSize:    <time in s>
    MovingWindowEnable:  <True..enable moving window, False..disable moving window>
    downsamplingMethod:  <peak, mean, subsample or off>

The configuration file is checked when it is loaded. Unknown keys, settings that do not
exist in a module and malformed remote widgets are reported in the log. Experiments that
reference experiment modules which are not registered are skipped.

For detailed information see the :ref:`chapter_examples` section.

defaults.sreg
-------------

The ``defaults.sreg`` file constitutes the standard configuration file for `PyWisp`. It uses a ``yaml`` syntax.
Below an example configuration with two experiments is presented:

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
        TimerTime: 40  # [] = ms, update interval of the GUI plots
        MovingWindowSize: 5  # [] = s
        MovingWindowEnable: True

In this example `Test` and `SeriesTrajectory` are derived :mod:`pywisp.experimentModules` classes. The settings below
of `Remote` configures a Push Button, that is connected to ´Value1` of the :mod:`pywisp.experimentModules` class
`Test`. The 'Config' section shows the settings for the plot configuration.

A `MultiButton` sets several parameters with a single click, e.g. as an emergency stop that sets the speed of
multiple motors to zero. Instead of `Module` and `Parameter` it has a list of `targets`, all of them are sent
to the bench at once:

.. code-block:: yaml

      Remote:
        Stop:
          widgetType: MultiButton
          shortcut: Esc
          targets:
            - {Module: Motor1, Parameter: speed, value: 0}
            - {Module: Motor2, Parameter: speed, value: 0}

In the widget editor the shortcut is recorded by pressing a key in the shortcut field, Backspace or Delete clear it.
Escape and Space can be used as shortcuts as well.

Own widget types can be added by deriving from :class:`pywisp.MovableWidget` and a Qt widget and registering the
class with :func:`pywisp.registerRemoteWidget`. The class defines its ``widgetType`` used in the config files, its
required and optional keys, how it is created from its config, the settings in the widget editor and the parameters
it sets when activated, see :class:`pywisp.widgets.remote.MovablePushButton` for an example. The config files, the
widget editor and the remote dock then handle the new type like the built in ones:

.. code-block:: python

    import pywisp as pw
    from pywisp.widgets.remote import MovablePushButton

    class Doubler(MovablePushButton):
        """ sends twice the configured value """
        widgetType = 'Doubler'

        def updates(self):
            return [(self.module, self.parameter, 2 * float(self.valueOn))]

    pw.registerRemoteWidget(Doubler)

For detailed information see the :ref:`chapter_examples` section.


