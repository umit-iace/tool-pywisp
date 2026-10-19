# -*- coding: utf-8 -*-
import random

import pytest

from pywisp.min import HDR, STF, Bytewise, HDRStuf, Packer, Unpacker
from pywisp.utils import coroutine, pipe


@coroutine
def collector(out):
    while True:
        out.append((yield))


def roundtrip(frames, garbage=b""):
    wire, out = [], []
    tx = pipe([Packer, lambda: collector(wire)])
    rx = pipe([Bytewise, HDRStuf, Unpacker, lambda: collector(out)])
    for f in frames:
        tx.send(f)
    rx.send(garbage)
    for w in wire:
        rx.send(w)
    return out


def test_header_bytes_in_payload_are_stuffed():
    out = roundtrip([(5, bytes([HDR] * 7)), (3, bytes([HDR, STF, HDR, HDR, STF]))])
    assert out == [(5, bytes([HDR] * 7)), (3, bytes([HDR, STF, HDR, HDR, STF]))]


def test_random_frames():
    rnd = random.Random(42)
    frames = [(rnd.randrange(64), bytes(rnd.choice([HDR, STF, 0, 1, 255]) for _ in range(rnd.randrange(40))))
              for _ in range(500)]
    assert roundtrip(frames) == frames


def test_resync_after_garbage():
    frames = [(1, b"abc"), (2, b"")]
    assert roundtrip(frames, garbage=bytes([HDR, 0x12, HDR, HDR, 0x34])) == frames


def test_corrupted_frame_is_dropped():
    wire, out = [], []
    tx = pipe([Packer, lambda: collector(wire)])
    rx = pipe([Bytewise, HDRStuf, Unpacker, lambda: collector(out)])
    tx.send((7, b"hello"))
    tx.send((8, b"world"))
    broken = bytearray(wire[0])
    broken[6] ^= 0x01
    rx.send(bytes(broken))
    rx.send(wire[1])
    assert out == [(8, b"world")]


def test_invalid_id_is_rejected():
    tx = pipe([Packer, lambda: collector([])])
    with pytest.raises(AssertionError):
        tx.send((64, b""))
