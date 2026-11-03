# -*- coding: utf-8 -*-
import socket

import pytest

from pywisp.connection import Connection, TcpConnection


@pytest.fixture
def tcp(qapp):
    conn = TcpConnection("127.0.0.1", 1, maxPayload=8)
    local, remote = socket.socketpair()
    conn.sock.close()
    conn.sock = local
    conn.connected = True
    received = []
    conn.received.connect(lambda frame: received.append((frame.id, frame.payload)))
    yield conn, remote, received
    local.close()
    remote.close()


def test_connection_is_abstract():
    with pytest.raises(TypeError):
        Connection(rx=None, tx=None)


def test_tcp_sender_pads_payload(tcp):
    conn, remote, _ = tcp
    conn.writeData({'id': 3, 'msg': b"ab"})
    assert remote.recv(100) == bytes([3]) + b"ab" + bytes(6)


def test_tcp_sender_survives_oversized_payload(tcp):
    conn, remote, _ = tcp
    conn.writeData({'id': 3, 'msg': bytes(9)})
    conn.writeData({'id': 4, 'msg': b"x"})
    assert remote.recv(100) == bytes([4]) + b"x" + bytes(7)
    assert conn.connected


def test_tcp_receiver_splits_chunks(tcp):
    conn, _, received = tcp
    frame1 = bytes([1]) + b"12345678"
    frame2 = bytes([2]) + b"abcdefgh"
    data = frame1 + frame2
    # deliver in odd sized chunks
    conn.worker.rx.send(data[:5])
    conn.worker.rx.send(data[5:13])
    conn.worker.rx.send(data[13:])
    # frames are handed on in batches
    assert received == []
    conn.worker.flush()
    assert received == [(1, b"12345678"), (2, b"abcdefgh")]


def test_frames_are_batched(tcp):
    conn, _, _ = tcp
    batches = []
    conn.receivedFrames.connect(batches.append)
    for i in range(5):
        conn.worker.rx.send(bytes([i]) + bytes(8))
    conn.worker.flush()
    conn.worker.flush()
    assert len(batches) == 1
    assert [f.id for f in batches[0]] == [0, 1, 2, 3, 4]


def test_tcp_peer_close_is_detected(tcp):
    conn, remote, _ = tcp
    remote.close()
    with pytest.raises(ConnectionResetError):
        conn._recv()


def test_tcp_connect_failure_returns_false(qapp):
    # nothing listens on this port
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    conn = TcpConnection("127.0.0.1", port)
    assert conn.open() is False
    assert not conn.connected


def test_tcp_connect_async(qtbot):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    conn = TcpConnection("127.0.0.1", server.getsockname()[1])
    try:
        with qtbot.waitSignal(conn.opened, timeout=5000) as blocker:
            conn.openAsync()
        assert blocker.args == [True]
        assert conn.connected and not conn.connecting
        with qtbot.waitSignal(conn.finished, timeout=5000):
            conn.close()
        assert not conn.connected
    finally:
        server.close()


def test_tcp_connect_async_failure(qtbot):
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    conn = TcpConnection("127.0.0.1", port)
    with qtbot.waitSignal(conn.opened, timeout=5000) as blocker:
        conn.openAsync()
    assert blocker.args == [False]
    assert not conn.connected


def test_connect_frames_are_sent_first(tcp):
    conn, remote, _ = tcp
    conn.connectFrames = [{'id': 62, 'msg': bytes([1, 1])}, {'id': 5, 'msg': b"x"}]
    conn.connecting = True
    conn._onOpened(True)
    assert remote.recv(100) == bytes([62, 1, 1]) + bytes(6) + bytes([5]) + b"x" + bytes(7)


def test_invalid_connect_frame_is_skipped(tcp):
    conn, remote, _ = tcp
    conn.connectFrames = [{'id': 62, 'msg': [1]}, {'id': 7, 'msg': b"ok"}]
    conn.connecting = True
    conn._onOpened(True)
    assert remote.recv(100) == bytes([7]) + b"ok" + bytes(6)
    assert conn.connected


def test_no_connect_frames_on_failure(tcp):
    conn, remote, _ = tcp
    conn.connectFrames = [{'id': 62, 'msg': bytes([1])}]
    conn.connecting = True
    remote.setblocking(False)
    conn._onOpened(False)
    with pytest.raises(BlockingIOError):
        remote.recv(100)
