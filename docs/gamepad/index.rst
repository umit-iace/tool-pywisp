Gamepad Support
===============

To control the remote widgets it is possible to use a gamepad. PyWisp uses the game controller
support of `SDL2 <https://www.libsdl.org>`_, which knows the layout of most common controllers
(PlayStation, Xbox, Switch and many more) on Windows, Linux and macOS. No additional drivers or
tools are needed. The SDL2 library is installed along with PyWisp by the ``pysdl2-dll`` package.

Connect the gamepad and select it in the menu ``Options`` → ``Select Gamepad``. When the gamepad
is unplugged, it is released and has to be selected again after reconnecting.

Assigning inputs
----------------

A remote widget is controlled by the input given in its ``shortcut-Gp`` entry. Push buttons and
switches need a button, sliders an axis. Axes deliver values between -0.5 and 0.5, which are mapped
onto the range of the slider.

.. code-block:: yaml

    Remote:
      Go:
        widgetType: PushButton
        Module: Test
        Parameter: Value1
        valueOn: '1'
        shortcut-Gp: S
      Speed:
        widgetType: Slider
        Module: Test
        Parameter: Value2
        minSlider: 0
        maxSlider: 10
        stepSlider: 0.5
        shortcut-Gp: X

The inputs are named by their position, the default mapping is:

========== ======================== =========================== =======================
Name       Input                    PlayStation                 Xbox
========== ======================== =========================== =======================
``N``      top face button          Triangle                    Y
``E``      right face button        Circle                      B
``S``      bottom face button       Cross                       A
``W``      left face button         Square                      X
``TL``     left shoulder button     L1                          LB
``TR``     right shoulder button    R1                          RB
``THL``    left trigger             L2                          LT
``THR``    right trigger            R2                          RT
``Select`` select button            Share / Create              View
``Start``  start button             Options                     Menu
``X``      left stick, horizontal
``Y``      left stick, vertical
``Z``      right stick, horizontal
``RZ``     right stick, vertical
``HX``     d-pad, horizontal
``HY``     d-pad, vertical
========== ======================== =========================== =======================

``X``, ``Y``, ``Z``, ``RZ``, ``HX`` and ``HY`` are axes, all others are buttons. Up and left give
negative values.

Changing the mapping
--------------------

To change the mapping, place a ``gamepad.yaml`` in the working directory. It maps names to the
inputs of the SDL standard layout, missing names keep their default:

.. code-block:: yaml

    # swap the face buttons like on a Nintendo controller
    N: x
    W: y
    S: b
    E: a

Available inputs are the buttons ``a``, ``b``, ``x``, ``y``, ``back``, ``guide``, ``start``,
``leftstick``, ``rightstick``, ``leftshoulder``, ``rightshoulder``, ``dpup``, ``dpdown``,
``dpleft``, ``dpright``, ``misc1``, ``paddle1`` to ``paddle4`` and ``touchpad``, the axes
``leftx``, ``lefty``, ``rightx``, ``righty``, ``lefttrigger`` and ``righttrigger`` as well
as ``dpad-x`` and ``dpad-y`` for the d-pad as axis.

The former files ``gpLinux.yaml`` and ``gpWin.yaml`` are no longer used.

Unsupported controllers
-----------------------

Controllers that SDL does not know are listed in the log when searching for gamepads. A mapping for
them can be added with a ``gamecontrollerdb.txt`` in the working directory, see the
`SDL_GameControllerDB <https://github.com/mdqinc/SDL_GameControllerDB>`_ project for a collection
of mappings and tools to create one.
