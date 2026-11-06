
import logging
from binascii import crc32
from enum import IntEnum
from dataclasses import dataclass
from struct import pack as spack, unpack as sunpack

from .utils import coroutine

HDR = 0xaa
STF = 0x55

#: largest frame id the MIN protocol can transmit
MAX_MIN_ID = 63
#: largest payload of a MIN frame in bytes: the rigs (tool-libs `Frame`) receive at most 128,
#: longer frames are dropped there without notice
MAX_MIN_PAYLOAD = 128

#: frame ids reserved for the system frames (control, status, 3..5 for future use), modules must not use them
SYSTEM_FRAME_IDS = range(1, 6)
#: frame id reserved for the control of the experiment
CONTROL_FRAME_ID = 1


class Control(IntEnum):
    """
    Payload of the control frames (id :data:`CONTROL_FRAME_ID`) sent to the rig.
    A control frame received from the rig signals a missed heartbeat.
    """
    STOP = 0
    START = 1
    HEARTBEAT = 2


def controlFrame(command):
    """ returns the frame for the given :class:`Control` command """
    return {'id': CONTROL_FRAME_ID, 'msg': bytes([Control(command)])}


def syncFrame(syncId):
    """
    Returns the sync command, sent after parameters changed during a run: the rig confirms the
    frames received since the last control frame with a status frame carrying `syncId`.
    Bits 0b110: rigs without sync support take it for a heartbeat.
    """
    return {'id': CONTROL_FRAME_ID, 'msg': bytes([0b110, syncId & 0xff])}


#: frame id reserved for the status the rig sends (tool-libs `Experiment::enableStatus`)
STATUS_FRAME_ID = 2


@dataclass
class RigStatus:
    """ content of a status frame (id :data:`STATUS_FRAME_ID`) of the rig """
    version: int
    #: experiment of the rig running
    running: bool
    #: bits defined by the project, named by the connection's `statusFlags`
    flags: int
    #: counts the start commands the rig received
    startSeq: int
    #: number and CRC32 of the frames the rig received before that start
    startCount: int
    startCrc: int
    #: uptime of the rig [ms]
    uptime: int
    #: id of the last sync command and number and CRC32 of the frames received before it,
    #: `None` if the rig does not support sync commands
    syncId: int = None
    syncCount: int = None
    syncCrc: int = None

    @classmethod
    def fromPayload(cls, payload):
        """ :return: the status or `None` if the payload is not a known status """
        if len(payload) < 14 or payload[0] != 1:
            return None
        version, state, flags, seq, count, crc, uptime = sunpack('<BBBBHII', payload[:14])
        status = cls(version, state == 1, flags, seq, count, crc, uptime)
        if len(payload) >= 21:
            status.syncId, status.syncCount, status.syncCrc = sunpack('<BHI', payload[14:21])
        return status


def frameCrc(frames, crc=0):
    """
    CRC32 over id, length and payload of each frame, as the rig computes it for the frames it
    received before a start command, control frames are not counted.

    :param frames: dicts with the keys 'id' and 'msg'
    :return: number of frames and CRC32
    """
    count = 0
    for frame in frames:
        if frame['id'] == CONTROL_FRAME_ID:
            continue
        crc = crc32(bytes([frame['id'], len(frame['msg'])]) + bytes(frame['msg']), crc)
        count += 1
    return count, crc

class Frame:
    def __init__(self, id, data):
        self.id = id
        self.payload = data
    @property
    def min_id(self): # backwards compatibility
        return self.id


@coroutine
def PackedPrinter():
    """ print packed data as coroutine. debug purposes only"""
    while True:
        f = yield
        print(f'packed {f}')

@coroutine
def FramePrinter():
    """ print unpacked data as coroutine. debug purposes only"""
    while True:
        f = yield
        print(f'unpacked {f.id} {f.payload}')

@coroutine
def Bytewise(sink):
    """ split received data into single bytes """
    while True:
        data = (yield)
        for d in data:
            sink.send(d)

@coroutine
def Packer(sink):
    """ pack received (id, data) for transmission on wire. coroutine """
    while True:
        id, data = (yield)
        if not 0 <= id <= MAX_MIN_ID or len(data) > MAX_MIN_PAYLOAD:
            # do not raise here, an exception would terminate the coroutine
            logging.getLogger("MIN").error(
                f"dropping frame {id}: ids must be in [0, {MAX_MIN_ID}] and payloads "
                f"must not exceed {MAX_MIN_PAYLOAD} bytes, got {len(data)} bytes")
            continue
        pld = bytes([id, len(data)]) + data
        crc = crc32(pld)
        ret = bytearray([HDR,HDR,HDR])
        hdcnt = 0
        for b in pld+spack('>I', crc):
            ret.append(b)
            if b == HDR:
                hdcnt += 1
                if hdcnt == 2:
                    ret.append(STF)
                    hdcnt = 0
            else:
                hdcnt = 0
        ret.append(STF)
        sink.send( bytes(ret) )

@coroutine
def HDRStuf(sink):
    """ Handle HDR and STF bytes of incoming stream """
    while True:
        b1 = (yield)
        if b1 != HDR:
            sink.send( (b1, True) )
            continue
        b2 = (yield)
        if b2 != HDR:
            sink.send( (b1, True) )
            sink.send( (b2, True) )
            continue
        b3 = (yield)
        if b3 == STF:
            sink.send( (b1, True) )
            sink.send( (b2, True) )
            continue
        elif b3 == HDR:
            sink.send( (0, False) )
            continue
        else:
            # something has gone wrong, give up
            sink.send( (0, False) )

@coroutine
def Unpacker(sink):
    """ unpack received data from wire into Frame. coroutine """
    while True:
        id, ok = (yield)
        if not ok: continue
        if id >= 64: # not handling transport frames
            # print(f"dropping transport frame: {id=}")
            continue
        length, ok = (yield)
        if not ok: continue
        pld = bytearray([])
        for _ in range(length):
            n, ok = (yield)
            if not ok: break
            pld.append(n)
        if not ok: continue
        c1, ok = (yield)
        if not ok: continue
        c2, ok = (yield)
        if not ok: continue
        c3, ok = (yield)
        if not ok: continue
        c4, ok = (yield)
        if not ok: continue
        crc = bytes([c1,c2,c3,c4])
        want = crc32(bytes([id, length])+pld)
        if spack('>I',want) != crc: # dropping frame
            # print(f"dropping frame mismatched CRC {id=}")
            continue
        sink.send( (id, bytes(pld) ))
        eof, ok = (yield)
        if eof != STF: # expected EOF==STF, but don't care
            pass
