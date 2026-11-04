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
      - Experiment Control (:data:`pywisp.min.CONTROL_FRAME_ID`):

        Payload (1 byte) sent to the rig is interpreted as (:class:`pywisp.min.Control`)

        - ``0`` -- STOP experiment
        - ``1`` -- START experiment
        - ``2`` -- HEARTBEAT

        A frame with this ID received from the rig signals a missed heartbeat and stops the experiment.

    * - 0, 2 - 63
      - User defined for connections using MIN (serial, UDP)
    * - 0, 2 - 255
      - User defined for the TCP connection

Frames returned by the experiment modules are checked before they are sent. Frames using the reserved ID 1, IDs
outside of 0 - 255 or a payload ``msg`` that is not ``bytes`` are rejected: when starting an experiment, the start is
aborted, later on the frame is dropped. In both cases the problem is logged. Frames exceeding the limits of MIN
(ID 63, payload 128 bytes, the size of a tool-libs ``Frame``) are dropped by the connection, also logged.

It is up to the user to guarantee that:

    * IDs are uniquely assigned
    * Every ID used to send data has a corresponding handler


Frames on connect
-----------------

A connection can send frames right after it has been established, before any other frame, e.g. to
tell a rig which role the client takes when the rig serves more than one kind of client. Set
:attr:`pywisp.connection.Connection.connectFrames` in the connection class, as a list of frames in the
format of the experiment modules:

.. code-block:: python

    from pywisp import connection

    class Connection(connection.UdpConnection):
        # tell the rig to run the experiments itself
        connectFrames = [{'id': 62, 'msg': bytes([1, 1])}]

        def __init__(self):
            super().__init__(ip="192.168.0.10", port=45670)

The frames are sent every time the connection is (re)established, also over UDP, where they let
the rig know where to send its data. Frames without an ``int`` id in 0 - 255 or with a ``msg`` that
is not ``bytes`` are logged and skipped. pywisp does not wait for an answer, the rig has to answer
or ignore them.

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
