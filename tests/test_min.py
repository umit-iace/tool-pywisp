# -*- coding: utf-8 -*-
import random

import pytest

from pywisp.min import (CONTROL_FRAME_ID, HDR, STATUS_FRAME_ID, STF, Bytewise, Control, HDRStuf, Packer, Unpacker,
                        controlFrame, syncFrame)
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


def test_packer_drops_invalid_frames(caplog):
    """ invalid frames are dropped without terminating the coroutine """
    out = roundtrip([(64, b"x"), (2, bytes(129)), (3, bytes(128)), (63, b"ok")])
    assert out == [(3, bytes(128)), (63, b"ok")]
    assert caplog.text.count("dropping frame") == 2


@pytest.mark.parametrize("command, payload", [(Control.STOP, 0), (Control.START, 1), (Control.HEARTBEAT, 2)])
def test_control_frames(command, payload):
    assert controlFrame(command) == {'id': CONTROL_FRAME_ID, 'msg': bytes([payload])}
    assert CONTROL_FRAME_ID == 1
    assert STATUS_FRAME_ID == 2


def test_system_frame_ids():
    from pywisp.min import SYSTEM_FRAME_IDS, SystemFrameId
    # same ids as tool-libs: 1 control, 2 status (Experiment::STATUS_ID), 3..5 reserved
    assert sorted(SYSTEM_FRAME_IDS) == [1, 2, 3, 4, 5]
    assert CONTROL_FRAME_ID is SystemFrameId.CONTROL and STATUS_FRAME_ID is SystemFrameId.STATUS
    assert 0 not in SYSTEM_FRAME_IDS and 6 not in SYSTEM_FRAME_IDS


def test_sync_frame_keeps_the_heartbeat_bit():
    # rigs without sync support take it for a heartbeat
    assert syncFrame(258) == {'id': CONTROL_FRAME_ID, 'msg': bytes([0b110, 2])}


@pytest.mark.parametrize("command", [7, 3, Control.SYNC, Control.START | Control.HEARTBEAT])
def test_control_frame_rejects_unknown_command(command):
    with pytest.raises(ValueError):
        controlFrame(command)
