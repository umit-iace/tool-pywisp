# -*- coding: utf-8 -*-
import logging
import struct

import pytest

from pywisp.min import LOG_FRAME_ID, LOG_MORE, STATUS_FRAME_ID, Frame, RigStatus, controlFrame, Control, frameCrc


def statusFrame(running=False, flags=0, seq=0, count=0, crc=0, uptime=1000, sync=None):
    """ sync: (id, count, crc) of the last sync command, None for a rig without sync support """
    payload = struct.pack('<BBBBHII', 1, running, flags, seq, count, crc, uptime)
    if sync is not None:
        payload += struct.pack('<BHI', *sync)
    return Frame(STATUS_FRAME_ID, payload)


# parameter frames sent before a start or sync command
FRAMES = [{'id': 20, 'msg': bytes([1, 2, 3])}, {'id': 21, 'msg': b''}]
COUNT, CRC = frameCrc(FRAMES)


def test_status_payload():
    status = RigStatus.fromPayload(statusFrame(True, 0b101, 3, 2, 0x12345678, 4242).payload)
    assert status == RigStatus(1, True, 0b101, 3, 2, 0x12345678, 4242)
    status = RigStatus.fromPayload(statusFrame(sync=(7, 2, 0xabc)).payload)
    assert (status.syncId, status.syncCount, status.syncCrc) == (7, 2, 0xabc)


def test_sync_frame():
    from pywisp.min import syncFrame
    # rigs without sync support take bits 0b110 for a heartbeat
    assert syncFrame(7) == {'id': 1, 'msg': bytes([0b110, 7])}


@pytest.mark.parametrize("payload", [b'', bytes(13), struct.pack('<BBBBHII', 2, 0, 0, 0, 0, 0, 0)])
def test_unknown_status_payload(payload):
    assert RigStatus.fromPayload(payload) is None


def test_frame_crc_as_the_rig():
    # same frames and value as tool-libs tests/status.cpp, control frames are not counted
    frames = [{'id': 20, 'msg': bytes([1, 2, 3])}, controlFrame(Control.HEARTBEAT), {'id': 21, 'msg': b''}]
    assert frameCrc(frames) == (2, 0x2af3ac7b)
    assert frameCrc([]) == (0, 0)


@pytest.fixture
def manager(qapp, cleanRegistry):
    from pywisp.connectionManager import ConnectionManager
    manager = ConnectionManager()
    manager.startTimeout = 200
    yield manager
    manager.disconnect()


def test_status_frames_are_taken_out(manager, qtbot):
    received = []
    manager.framesReceived.connect(received.extend)
    assert manager.isResponding() is None
    with qtbot.waitSignal(manager.rigStatusChanged) as blocker:
        manager._onFrames([statusFrame(), Frame(15, b'data')])
    assert blocker.args == []
    assert [f.id for f in received] == [15]
    assert manager.isResponding() is True


def test_rig_stops_responding(manager, qtbot, monkeypatch):
    manager._onFrames([statusFrame()])
    import pywisp.connectionManager as cm
    now = cm.time.monotonic()
    monkeypatch.setattr(cm.time, 'monotonic', lambda: now + 2)
    with qtbot.waitSignal(manager.rigStatusChanged, timeout=1000):
        pass
    assert manager.isResponding() is False


def test_start_confirmed(manager, qtbot):
    manager._onFrames([statusFrame(seq=4)])
    assert manager.expectStart(FRAMES)
    # older status without the new start is not yet a confirmation
    manager._onFrames([statusFrame(seq=4)])
    with qtbot.waitSignal(manager.startConfirmed, timeout=500):
        manager._onFrames([statusFrame(True, seq=5, count=COUNT, crc=CRC)])


def test_start_with_other_parameters_fails(manager, qtbot):
    manager._onFrames([statusFrame(seq=4)])
    manager.expectStart(FRAMES)
    with qtbot.waitSignal(manager.startFailed, timeout=500) as blocker:
        manager._onFrames([statusFrame(True, seq=5, count=1, crc=CRC)])
    assert '1 frames' in blocker.args[0]


def test_start_without_confirmation_fails(manager, qtbot):
    manager._onFrames([statusFrame(seq=4)])
    manager.expectStart(FRAMES)
    with qtbot.waitSignal(manager.startFailed, timeout=1000) as blocker:
        pass
    assert 'no confirmation' in blocker.args[0]


def test_rigs_without_status_are_not_checked(manager):
    assert not manager.expectStart(FRAMES)


def test_sync_confirmed(manager, qtbot):
    sent = []
    manager.write = sent.append
    manager._onFrames([statusFrame(True, sync=(0, 0, 0))])
    syncId = manager.sync(FRAMES)
    assert syncId == 1
    assert sent == [{'id': 1, 'msg': bytes([0b110, 1])}]
    # periodic status of the old sync is no answer yet
    manager._onFrames([statusFrame(True, sync=(0, 0, 0))])
    with qtbot.waitSignal(manager.syncConfirmed, timeout=500) as blocker:
        manager._onFrames([statusFrame(True, sync=(1, COUNT, CRC))])
    assert blocker.args == [1]


def test_sync_with_other_parameters_fails(manager, qtbot):
    manager.write = lambda data: None
    manager._onFrames([statusFrame(True, sync=(0, 0, 0))])
    syncId = manager.sync(FRAMES)
    with qtbot.waitSignal(manager.syncFailed, timeout=500) as blocker:
        manager._onFrames([statusFrame(True, sync=(syncId, 1, 0x123))])
    assert blocker.args[0] == syncId
    assert '1 frames' in blocker.args[1]


def test_sync_without_confirmation_fails(manager, qtbot):
    manager.write = lambda data: None
    manager._onFrames([statusFrame(True, sync=(0, 0, 0))])
    syncId = manager.sync(FRAMES)
    with qtbot.waitSignal(manager.syncFailed, timeout=1500) as blocker:
        pass
    assert blocker.args[0] == syncId
    assert 'no confirmation' in blocker.args[1]


def test_rigs_without_sync_support_get_no_sync(manager):
    sent = []
    manager.write = sent.append
    manager._onFrames([statusFrame(True)])
    assert manager.sync(FRAMES) is None
    assert sent == []


def test_sync_ids_wrap_without_zero(manager):
    manager.write = lambda data: None
    manager._onFrames([statusFrame(True, sync=(0, 0, 0))])
    manager._syncId = 254
    assert [manager.sync([]) for _ in range(3)] == [255, 1, 2]


def test_tcp_rig_receives_padded_frames(manager, qtbot):
    from pywisp.connection import TcpConnection
    conn = TcpConnection('127.0.0.1', 1, maxPayload=8)
    # payloads are padded to maxPayload, longer ones are not sent at all
    assert conn.rigFrame({'id': 20, 'msg': b'ab'}) == {'id': 20, 'msg': b'ab' + bytes(6)}
    assert conn.rigFrame({'id': 20, 'msg': bytes(9)}) is None
    manager.connection = conn
    frames = FRAMES + [{'id': 22, 'msg': bytes(9)}]
    count, crc = frameCrc([conn.rigFrame(f) for f in FRAMES])
    assert crc != CRC
    manager._onFrames([statusFrame(seq=4)])
    manager.expectStart(frames)
    with qtbot.waitSignal(manager.startConfirmed, timeout=500):
        manager._onFrames([statusFrame(True, seq=5, count=count, crc=crc)])


def logFrame(level, text, more=False):
    return Frame(LOG_FRAME_ID, bytes([level | (LOG_MORE if more else 0)]) + text.encode())


def rigRecords(caplog):
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == "Rig"]


@pytest.mark.parametrize("level, pyLevel", [(0, logging.INFO), (1, logging.INFO), (2, logging.WARNING),
                                            (3, logging.ERROR), (42, logging.WARNING)])
def test_log_frame(manager, caplog, level, pyLevel):
    caplog.set_level(logging.INFO)
    received = []
    manager.framesReceived.connect(received.extend)
    manager._onFrames([logFrame(level, "hällo\n"), Frame(15, b'data')])
    assert rigRecords(caplog) == [(pyLevel, "hällo")]
    assert [f.id for f in received] == [15]


def test_log_frame_parts_are_joined(manager, caplog):
    caplog.set_level(logging.INFO)
    manager._onFrames([logFrame(2, "first ", more=True)])
    assert rigRecords(caplog) == []
    manager._onFrames([Frame(LOG_FRAME_ID, b''), logFrame(2, "second")])
    assert rigRecords(caplog) == [(logging.WARNING, "first second")]


def test_log_frame_tcp_padding_is_stripped(manager, caplog):
    caplog.set_level(logging.INFO)
    pad = bytes(40)
    manager._onFrames([Frame(LOG_FRAME_ID, bytes([1 | LOG_MORE]) + b"a" + pad),
                       Frame(LOG_FRAME_ID, bytes([1]) + b"b" + pad)])
    assert rigRecords(caplog) == [(logging.INFO, "ab")]


def test_log_frame_too_long_is_dropped(manager, caplog):
    caplog.set_level(logging.INFO)
    manager._onFrames([logFrame(1, "x" * 127, more=True)] * 9 + [logFrame(1, "end"), logFrame(1, "next")])
    assert rigRecords(caplog) == [(logging.INFO, "next")]
    assert "dropped" in caplog.text
