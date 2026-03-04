Transport Layer
===============

To handle all communication interfaces for B&R, Raspberry Pi, Arduino, ... on the same way a middle layer is implemented
called `Transport-Layer`. Additionally to this for the data handling the frame based protocol
`MIN-Protocol <https://github.com/min-protocol/min>`_ is used.

Currently only for wired serial connected devices, like Arduino or STMs, the `MIN-Protocol` itself is used.
On devices where a `TCP`-based approach or a wifi serial connection is used, only the frame handling by `MIN` is
applied.

MIN-Frame
---------

The smallest unit in the communication stack, each `MIN-Frame` data has the structure:

.. list-table::
    :widths: 50 50
    :header-rows: 1

    * - ID
      - Payload
    * - unique identifier, packed as one byte
      - data, packed as byte array

Note that the maximum possible length of a frame differs on each device.
On `Arduino UNO` the limit is at 50 bytes due to the internal memory.
When manually packing the frames, this limit should be respected otherwise
packet loss may occur.

Frame IDs
---------

.. list-table::
    :widths: 50 50
    :header-rows: 1

    * - ID
      - Meaning
    * - 0
      - Unknown
    * - 1
      - Experiment Control:

        * If byte 1 is set: Heartbeat packet from PyWisp
        * Else: read byte 0 as desired alive state

    * - 2 - 9
      - Unknown / Reserved?
    * - 10 - 255
      - User defined


Packing a frame
---------------

To send data to the test rig, it has to ba packed into MIN-Frames before it can be handed over
to the connection.
Using the :mod:`struct` module from the standard library, the payload can be created as follows

.. literalinclude:: ../../examples/generic/visu/trajectory.py
   :language: python
   :lines: 27-29

However, if more than just a handful of parameters are to be sent (for example when sending the interpolation points of
a trajectory), the helper function :meth:`pywisp.utils.packArrayToFrame` may be used:

.. literalinclude:: ../../examples/generic/visu/trajectory.py
   :language: python
   :lines: 31-34

In the end it is up to the user to guarantee that:

    * No system reserved IDs are used
    * None of several ExperimentModules do use the same frame ID
    * Every frame ID used on the rig or the remote has an appropriate
      handler on the other side


Unpacking a frame
-----------------

When a frame is received by pywisp, it has to be unpacked to further process the information therein.

.. literalinclude:: ../../examples/generic/visu/trajectory.py
   :language: python
   :lines: 38-45

Note that currently no logic is available in pywisp to unpack a series of frames
and join them into one set of measurements.
