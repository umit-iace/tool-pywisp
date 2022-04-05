
from binascii import crc32
from struct import pack as spack

from .utils import coroutine

HDR = 0xaa
STF = 0x55

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
        print(f'unpacked {f.id=} {f.payload=}')

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
        assert(id < 64)
        assert(len(data) < 256)
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
def Unpacker(sink):
    """ unpack received data from wire into Frame. coroutine """
    while True:
        if (yield)!= HDR:
            continue
        if (yield)!= HDR:
            continue
        if (yield)!= HDR:
            continue
        id = (yield)
        assert(id < 64)
        len = (yield)
        hdcnt = 0
        pld = bytearray([])
        for _ in range(len):
            n = (yield)
            pld.append(n)
            if n == HDR:
                hdcnt += 1
                if hdcnt == 2:
                    (yield)
                    hdcnt = 0
            else:
                hdcnt = 0
        crc = bytes([(yield),(yield),(yield),(yield)])
        want = crc32(bytes([id, len])+pld)
        if spack('>I',want) != crc:
            continue
        sink.send( Frame(id, bytes(pld) ))
