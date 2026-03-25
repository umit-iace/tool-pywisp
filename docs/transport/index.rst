.. _communication_layer:

Communication Layer
===============

To handle all communication interfaces for the different underlying hardwares in a similar way,
a communication protocol is introduced.
This is based on the `MIN-Protocol <https://github.com/min-protocol/min>`_.

Currently the ``MIN``-specified frame packing is not used on `TCP`-based interfaces.

MIN-Frame
---------

The smallest unit in the communication stack, each ``Frame`` has the structure:

.. list-table::
    :widths: 50 50
    :header-rows: 1

    * - ID
      - Payload
    * - unique identifier, packed as a 7-bit value (``0x0`` - ``0x7f``)
      - data, packed as little-endian byte array

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
    * - 1
      - Experiment Control:

        Payload (1 byte) is interpreted as

        - ``0`` -- STOP experiment
        - ``1`` -- START experiment
        - ``2`` -- HEARTBEAT

    * - 0, 2 - 127
      - User defined

It is up to the user to guarantee that:

    * No system reserved IDs are used
    * IDs are uniquely assigned
    * Every ID used to send data has a corresponding handler


Packing a frame
---------------

To send data to the test rig, it has to be packed into MIN-Frames before it can be handed over
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


Unpacking a frame
-----------------

When a frame is received by PyWisp, it has to be unpacked to further process the information therein.

.. literalinclude:: ../../examples/generic/visu/trajectory.py
   :language: python
   :lines: 38-45

Note that currently no logic is available in PyWisp to unpack a series of frames
and join them into one set of measurements.
