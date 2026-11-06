.. _communication_layer:

Communication Layer
===================

To handle all communication interfaces for the different underlying hardwares in a similar way,
a communication protocol is introduced.
This is based on the `MIN-Protocol <https://github.com/min-protocol/min>`_.

Serial and UDP connections pack the frames with ``MIN``. TCP already delivers a reliable byte stream, so
:class:`pywisp.connection.TcpConnection` sends every frame as a fixed size record instead, see
:ref:`tcp_framing`.

MIN-Frame
---------

The smallest unit in the communication stack, each ``Frame`` has the structure:

.. list-table::
    :widths: 50 50
    :header-rows: 1

    * - ID
      - Payload
    * - unique identifier, 6 bits with MIN (``0`` - ``63``), one byte over TCP
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

    * - 63
      - Rig status (:data:`pywisp.min.STATUS_FRAME_ID`), sent by the rig, see
        :ref:`rig_status`
    * - 0, 2 - 62
      - User defined
    * - 64 - 255
      - Only over TCP to rigs that are not built on tool-libs (e.g. the B&R example), the frame registry of
        tool-libs dispatches ids 0 - 63 only

Frames returned by the experiment modules are checked before they are sent. Frames using the reserved ID 1, IDs
outside of 0 - 255 or a payload ``msg`` that is not ``bytes`` are rejected: when starting an experiment, the start is
aborted, later on the frame is dropped. In both cases the problem is logged. Frames exceeding the limits of MIN
(ID 63, payload 128 bytes, the size of a tool-libs ``Frame``) are dropped by the connection, also logged. Over TCP
the limit is ``maxPayload`` (80 bytes).

.. _tcp_framing:

Frames over TCP
---------------

:class:`pywisp.connection.TcpConnection` sends and receives every frame as a record of ``1 + maxPayload`` bytes:
one byte id, then the payload padded with zeros to ``maxPayload`` (default 80). There is no checksum and no
resynchronisation, longer payloads are dropped and logged. The receiver gets the full padded payload, so unpack it
with :func:`struct.unpack_from` instead of :func:`struct.unpack`. Both sides have to use the same ``maxPayload``.

On a rig built on tool-libs this is the ``TCP`` transport (``sys/comm.h``, Linux only, a server for one client at a
time: the next client is accepted once the last one disconnected, data sent while no client is connected is dropped)
wrapped in ``FixedFrame<80>`` (``comm/fixedframe.h``), which is used like ``Min``. Both need a tool-libs version that
contains them, PyWisp's examples and tests build against :data:`pywisp.TOOL_LIBS_VERSION`.

A rig can serve UDP and TCP at the same time by feeding the frames of both into one frame registry and answering over
the link the last frame came from, as the simulation of the generic example does
(``examples/generic/sim/sim.cpp``):

.. literalinclude:: ../../examples/generic/sim/sim.cpp
   :language: c++
   :start-at: UDP udp
   :end-at: FixedFrame<> tcpFrames

.. literalinclude:: ../../examples/generic/sim/sim.cpp
   :language: c++
   :start-at: /** frames to pywisp
   :end-before: Support::Support

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
   :lines: 26-28

However, if more than just a handful of parameters are to be sent (for example when sending the interpolation points of
a trajectory), the helper function :meth:`pywisp.utils.packArrayToFrame` may be used:

.. literalinclude:: ../../examples/generic/visu/trajectory.py
   :language: python
   :lines: 30-33


Unpacking a frame
-----------------

When a frame is received by PyWisp, it has to be unpacked to further process the information therein.

.. literalinclude:: ../../examples/generic/visu/trajectory.py
   :language: python
   :lines: 37-47

Note that currently no logic is available in PyWisp to unpack a series of frames
and join them into one set of measurements.
