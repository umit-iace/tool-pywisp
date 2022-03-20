
from binascii import crc32
from struct import pack as spack

__all__ = ["Min"]

HDR = 0xaa
STF = 0x55

def PackedPrinter():
    """ print packed data as coroutine. debug purposes only"""
    while True:
        f = yield
        print(f'packed {f}')

def UnpackedPrinter():
    """ print unpacked data as coroutine. debug purposes only"""
    while True:
        f = yield
        print(f'unpacked id:{f[0]} data:{f[1]}')

class Min:
    """
    min-style packing and unpacking of data as coroutines
    """
    def __init__(self, packed, unpacked):
        """
        packed: min-packed data will be sent to this coroutine
        unpacked: unpacked
        """
        self.u = Unpacker(unpacked)
        self.p = Packer(packed)
        next(packed)
        next(unpacked)
        next(self.p)
        next(self.u)

    def unpack(self, data):
        for d in data:
            self.u.send(d)

    def pack(self, id, data):
        self.p.send((id,data))

def Packer(receiver):
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
        receiver.send( bytes(ret) )

def Unpacker(receiver):
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
        receiver.send( (id, bytes(pld) ))
