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

Some IDs mean different things depending on who sends the frame, so the table lists both directions.

.. list-table::
    :widths: 14 43 43
    :header-rows: 1

    * - ID
      - Sent by PyWisp to the rig
      - Sent by the rig to PyWisp
    * - 1
      - Experiment control (:data:`pywisp.min.CONTROL_FRAME_ID`): start, stop, heartbeat and sync, see
        :ref:`control_frame`
      - The rig stopped the experiment by itself (first payload byte ``0``, the optional second byte is the
        reason, see :ref:`control_frame`). PyWisp stops the experiment in the GUI and keeps the connection, the
        frame has arrived after all.
    * - 2
      - not used
      - Rig status (:data:`pywisp.min.STATUS_FRAME_ID`), see :ref:`rig_status`
    * - 3
      - not used
      - Rig log (:data:`pywisp.min.LOG_FRAME_ID`), sent when the rig logs a message: payload ``[hdr][text...]``,
        ``hdr`` bits 0..6 the level (0 none, 1 info, 2 warn, 3 error), bit 7 another part follows, the text raw
        UTF-8 (at most 127 bytes per frame), see :ref:`rig_log`
    * - 4 - 5
      - Reserved for future system frames
      - Reserved for future system frames
    * - 0, 6 - 63
      - User defined: parameters of the experiment modules
        (:meth:`~pywisp.experimentModules.ExperimentModule.getParams` and friends)
      - User defined: data of the rig, decoded by
        :meth:`~pywisp.experimentModules.ExperimentModule.handleFrame`
    * - 64 - 255
      - Only over TCP to rigs that are not built on tool-libs (e.g. the B&R example), the frame registry of
        tool-libs dispatches ids 0 - 63 only
      - Same as for the other direction

.. _control_frame:

Control frame
-------------

The first payload byte of a control frame sent to the rig is a set of bit flags (:class:`pywisp.min.Control`), not
a single command:

.. list-table::
    :widths: 14 14 72
    :header-rows: 1

    * - Bit
      - Flag
      - Meaning
    * - 0
      - ``START``
      - set: start the experiment, cleared (``STOP``, value ``0``): stop it
    * - 1
      - ``HEARTBEAT``
      - keep the running experiment alive, without one within the heartbeat timeout the rig stops it. PyWisp
        sends it while connected, every :attr:`~pywisp.connection.Connection.heartbeatInterval` (500 ms) while idle
        and every ``HeartbeatTime`` during a run, ``0`` sends none
    * - 2
      - ``SYNC``
      - confirm the frames received since the last control frame with a status frame, the second payload byte
        is the sync id, see :ref:`rig_status`

The rig acts on the highest set bit only: ``SYNC`` before ``HEARTBEAT`` before ``START``/``STOP``. So ``3``
(``START | HEARTBEAT``) is a heartbeat and does not start anything. PyWisp sends these payloads:

.. list-table::
    :widths: 28 72
    :header-rows: 1

    * - Payload
      - Sent by
    * - ``0``
      - :func:`pywisp.min.controlFrame` with ``Control.STOP``
    * - ``1``
      - :func:`pywisp.min.controlFrame` with ``Control.START``
    * - ``2``
      - :func:`pywisp.min.controlFrame` with ``Control.HEARTBEAT``
    * - ``6``, sync id
      - :func:`pywisp.min.syncFrame`: ``SYNC | HEARTBEAT``, so rigs without sync support take it for a heartbeat

A control frame sent by the rig reports that the rig stopped the experiment by itself. Its first payload byte is
``0``, the optional second byte is the reason:

.. list-table::
    :widths: 28 72
    :header-rows: 1

    * - Reason
      - Meaning
    * - missing or ``0``
      - the rig missed the heartbeat (tool-libs ``Experiment::setHeartbeatTimeout``, the B&R example server)
    * - ``1`` - ``255``
      - the rig stopped the experiment because of an error, the value is a rig specific error code

PyWisp stops the experiment in the GUI, keeps the connection, logs the reason and shows it in the tooltip of the
connection light ("the rig missed the heartbeat and stopped the experiment" or "the rig stopped the experiment
(error code n)"). It does not restart the experiment. Applications can connect to
:attr:`pywisp.experiments.ExperimentInteractor.rigStopped`, which carries the reason.

Frames returned by the experiment modules are checked before they are sent. Frames using the reserved system IDs
1 - 5 (:class:`pywisp.min.SystemFrameId`), IDs outside of 0 - 255 or a payload ``msg`` that is not ``bytes`` are
rejected: when starting an experiment, the start is aborted, later on the frame is dropped. In both cases the problem is logged. Frames exceeding the limits of MIN
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

A connection can check the answer in :meth:`pywisp.connection.Connection.filterFrames`, which gets every batch of
received frames before they are passed on and returns the frames to pass on. It may close the connection, e.g. if
the rig refuses the session. Frames it does not return do not count as the answer of the rig, so a connection
closed while connecting ends as "No connection ... established". Errors in it are logged and the frames are
passed on unchanged.

.. code-block:: python

    class Connection(connection.UdpConnection):
        connectFrames = [{'id': 62, 'msg': bytes([1, 1])}]

        def filterFrames(self, frames):
            # the rig answers with id 62, payload 0: session refused
            if any(f.id == 62 and f.payload[0] == 0 for f in frames):
                self._logger.error("the rig refused the session")
                self.close()
                return []
            return frames

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
