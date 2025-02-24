
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
        len, ok = (yield)
        if not ok: continue
        pld = bytearray([])
        for _ in range(len):
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
        want = crc32(bytes([id, len])+pld)
        if spack('>I',want) != crc: # dropping frame
            # print(f"dropping frame mismatched CRC {id=}")
            continue
        sink.send( (id, bytes(pld) ))
        eof, ok = (yield)
        if eof != STF: # expected EOF==STF, but don't care
            pass
