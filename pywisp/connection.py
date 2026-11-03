# -*- coding: utf-8 -*-
"""
This module contains all classes and functions related to establishing a connection with a test rig.
"""

import logging
import socket
import time
from abc import ABCMeta, abstractmethod

import serial
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from .min import Packer, Unpacker, Frame, Bytewise, HDRStuf
from .utils import coroutine, pipe

__all__ = ["Connection", "UdpConnection", "TcpConnection", "SerialConnection"]


class ConnReader(QObject):
    """
    Thread worker receiving connection data.

    Received frames are collected and handed to the gui thread in batches, since
    emitting a queued signal for every single frame does not scale to high frame rates.
    """
    err = pyqtSignal(str)
    frames = pyqtSignal(object)
    # result of establishing the connection in the thread, see Connection.openAsync
    opened = pyqtSignal(bool)
    # [s] maximum time frames are held back before they are passed on
    flushInterval = 0.01

    def __init__(self, conn, rx):
        super().__init__()
        self.conn = conn
        self.stop = False
        self.pending = []
        # establish the connection in the thread before receiving
        self.connectFirst = False
        self.rx = pipe([rx, self.collector])

    @coroutine
    def collector(self):
        """ collect unpacked frames until the next flush """
        while True:
            id, payload = yield
            self.pending.append(Frame(id, payload))

    def flush(self):
        """ pass all collected frames on """
        if self.pending:
            frames, self.pending = self.pending, []
            self.frames.emit(frames)

    def run(self):
        if self.connectFirst:
            ok = self.conn._connect()
            self.opened.emit(ok)
            if not ok:
                return
        lastFlush = time.monotonic()
        while not self.stop:
            try:
                data = self.conn._recv()
                if data:
                    self.rx.send(data)
            except (TimeoutError, socket.timeout):
                # intentionally empty
                pass
            except Exception as e:
                if not self.stop:
                    self.err.emit(f"connection dropped: {repr(e)} / {e}")
                break

            now = time.monotonic()
            if now - lastFlush >= self.flushInterval:
                self.flush()
                lastFlush = now
        self.flush()

    def quit(self):
        self.stop = True


class ConnectionMeta(ABCMeta, type(QObject)):
    pass


class Connection(QObject, metaclass=ConnectionMeta):
    """
    Base class for a connection, i.e. tcp or serial

    A connection instance can only be opened once. After :meth:`close` a new
    instance has to be created.
    """
    #: emitted for every received frame, prefer :attr:`receivedFrames` for high frame rates
    received = pyqtSignal(Frame)
    #: emitted with a list of all frames received since the last emission
    receivedFrames = pyqtSignal(object)
    finished = pyqtSignal()
    #: result of :meth:`openAsync`, `True` if the connection has been established
    opened = pyqtSignal(bool)
    # [ms] time to wait for the reader thread when closing
    closeTimeout = 1000
    # connections closed while connecting keep themselves alive until their thread has ended,
    # destroying a running QThread aborts the process
    _aborting = set()
    #: frames sent right after the connection has been established, before anything else,
    #: e.g. to tell the rig which role this client takes. A list of dicts with the keys 'id' and
    #: 'msg' (bytes), as returned by the experiment modules. Set it in the subclass:
    #: ``connectFrames = [{'id': 62, 'msg': bytes([1, 1])}]``
    connectFrames = ()

    def __init__(self, rx, tx, *args, **kwargs):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tx = pipe([tx, self._send])
        thread = QThread()
        worker = ConnReader(self, rx)
        worker.moveToThread(thread)
        worker.err.connect(self.workerError)
        worker.frames.connect(self._onFrames)
        worker.opened.connect(self._onOpened)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self.readerThread = thread
        self.worker = worker
        self.connected = False
        # openAsync has been called and the result is not known yet
        self.connecting = False
        self._aborted = False

    def workerError(self, err):
        self.worker.deleteLater()
        self._logger.error(err)
        self.close()

    def _onFrames(self, frames):
        """
        pass received frames to the application, runs in the thread of the connection object
        """
        self.receivedFrames.emit(frames)
        if self.receivers(self.received):
            for frame in frames:
                self.received.emit(frame)

    def rigFrame(self, frame):
        """
        the frame as the rig receives it, for the check of the received frames, see
        :meth:`pywisp.connectionManager.ConnectionManager.expectStart`

        :param frame: dict with the keys 'id' and 'msg'
        :return: the received frame or `None` if the frame is not sent at all
        """
        return frame

    def writeData(self, data):
        """
        push application data through min
        """
        if not self.connected:
            return
        try:
            self.tx.send((data['id'], data['msg']))
        except TimeoutError:
            pass
        except Exception as e:
            self._logger.error(f"cannot send data: {e}")
            self.close()

    def open(self):
        """
        establish the connection, blocks until the connection is established or has failed.
        Use :meth:`openAsync` in the gui.
        """
        if self._connect():
            self.readerThread.start()
            self.connected = True
            self._sendConnectFrames()
            return True
        return False

    def openAsync(self):
        """
        establish the connection in the reader thread, so a slow or unreachable rig does
        not block the gui. The result is emitted with :attr:`opened`.
        """
        self.connecting = True
        self.worker.connectFirst = True
        self.readerThread.start()

    def _onOpened(self, ok):
        """ result of the connection attempt of the reader thread, runs in the thread of the connection """
        self.connecting = False
        if self._aborted:
            # closed while connecting, the worker has already been asked to stop
            self._stopThread()
            self._finishAborted()
            return
        self.connected = ok
        if not ok:
            self._stopThread()
        else:
            self._sendConnectFrames()
        self.opened.emit(ok)

    def _sendConnectFrames(self):
        """ send :attr:`connectFrames`, invalid ones are logged and skipped """
        for frame in self.connectFrames:
            id, msg = frame.get('id'), frame.get('msg')
            if not isinstance(id, int) or not 0 <= id <= 255 or not isinstance(msg, bytes):
                self._logger.error(f"invalid connect frame {frame}, needs an int 'id' and bytes 'msg'")
                continue
            self.writeData(frame)

    def close(self):
        """ close the connection, stop worker and thread """
        if self.connecting:
            # the result of the connection attempt is handled in _onOpened
            self._aborted = True
            self.worker.quit()
            Connection._aborting.add(self)
            return
        if not self.connected:
            return
        self.connected = False
        self.worker.quit()
        self._disconnect()
        self._stopThread()
        self.finished.emit()

    @classmethod
    def waitForAborted(cls, timeout=5000):
        """
        wait until the connections closed while connecting have ended, e.g. before the application quits

        :param timeout: [ms] maximum time to wait for every connection
        :return: `True` if all of them have ended
        """
        for conn in list(cls._aborting):
            try:
                # the event loop of the thread keeps running after the worker has returned
                conn.readerThread.quit()
                if not conn.readerThread.wait(timeout):
                    continue
            except RuntimeError:
                # the thread has already been deleted on the C++ side
                pass
            conn._finishAborted()
        return not cls._aborting

    def _finishAborted(self):
        """ close a connection that has been closed while connecting, once its thread has ended """
        if self not in Connection._aborting:
            return
        # closing a socket or port that has not been opened is fine
        self._disconnect()
        Connection._aborting.discard(self)

    def _stopThread(self):
        try:
            self.readerThread.quit()
            # the receive loop polls with a short timeout, so the thread ends quickly
            if not self.readerThread.wait(self.closeTimeout):
                self._logger.warning("the reader thread did not stop in time")
        except RuntimeError:
            # the thread has already ended and been deleted on the C++ side
            pass

    @abstractmethod
    def _connect(self):
        pass

    @abstractmethod
    def _disconnect(self):
        pass

    @abstractmethod
    def _recv(self) -> bytes:
        """
        return data from connection.
        this runs in a threaded loop.
        make sure this actually takes some time (e.q. w/ socket timeouts)
        otherwise this will eat your cpu.
        raise an exception if the connection has been closed by the other side.
        """
        pass

    @abstractmethod
    @coroutine
    def _send(self):
        """ write data out to the connection. coroutine. """
        pass


class SerialConnection(Connection):
    """
    Simple Serial Connection
    """

    supportedBaudrates = (
            1200, 1800, 2400, 4800, 9600, 
            19200, 38400, 57600, 
            115200, 230400, 460800, 500000, 576000, 921600,
            1000000, 1152000, 1500000, 2000000, 2500000, 3000000, 3500000,4000000,
            )
    # former name, kept for compatibility
    supported_baudrates = supportedBaudrates

    def __init__(self, port: str, baud: int):
        self.serial = serial.Serial(timeout=0.01)
        if baud not in self.supportedBaudrates:
            raise ValueError(f"Baudrate {baud} not supported. " 
                             f"Choose one of {self.supportedBaudrates}")
        self.serial.baudrate = baud
        self.serial.port = port
        super().__init__(tx=Packer, rx=[Bytewise, HDRStuf, Unpacker])

    def _connect(self):
        try:
            self.serial.open()
        except Exception as e:
            self._logger.error(f'cannot connect: {e}')
            self.serial.close()
            return False
        return True

    def _disconnect(self):
        self.serial.close()

    def _recv(self):
        return self.serial.read(512)

    @coroutine
    def _send(self):
        while True:
            data = yield
            self.serial.write(data)


class SocketConnection(Connection):
    """
    Simple Socket based Connection
    """

    def __init__(self, socket, ip, port, timeout=0.01, connectTimeout=3.0, **kwargs):
        self.ip = ip
        self.port = port
        self.sock = socket
        self.timeout = timeout
        self.connectTimeout = connectTimeout
        super().__init__(**kwargs)

    def _connect(self):
        try:
            # use a generous timeout while connecting, the short one is only
            # meant for the polling receive loop
            self.sock.settimeout(self.connectTimeout)
            self.sock.connect((self.ip, int(self.port)))
            self.sock.settimeout(self.timeout)
        except OSError as e:
            self._logger.error(f"Connection to the server is not possible: {e}")
            self.sock.close()
            return False
        return True

    def _disconnect(self):
        self.sock.close()

    def _recv(self):
        data = self.sock.recv(512*4)
        if not data and self.sock.type == socket.SOCK_STREAM:
            # an empty read on a stream socket means the peer closed the connection
            raise ConnectionResetError("connection closed by peer")
        return data

    @coroutine
    def _send(self):
        while True:
            data = yield
            self.sock.sendall(data)


class TcpConnection(SocketConnection):
    """
    Simple Tcp Connection
    """

    def __init__(self, ip, port, maxPayload=80, **kwargs):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.maxPayload = maxPayload

        @coroutine
        def Sender(sink):
            """ send 1 byte id + 80 byte payload """
            while True:
                id, data = (yield)
                if len(data) > maxPayload:
                    # do not raise here, an exception would terminate the coroutine
                    logging.getLogger("TcpConnection").error(
                        f"dropping frame {id}: payload of {len(data)} bytes "
                        f"exceeds maxPayload={maxPayload}")
                    continue
                sink.send(bytes([id]) + data + bytes(maxPayload - len(data)))

        @coroutine
        def Receiver(sink):
            """ receive 81 byte chunks -> (1 id + 80 payload) """
            data = bytearray()
            while True:
                data.extend((yield))
                while len(data) >= maxPayload + 1:
                    f = data[:maxPayload + 1]
                    del data[:maxPayload + 1]
                    sink.send((f[0], bytes(f[1:])))

        super().__init__(sock, ip, port, tx=Sender, rx=Receiver, **kwargs)

    def rigFrame(self, frame):
        """ the rig receives every payload padded to `maxPayload`, longer ones are dropped """
        if len(frame['msg']) > self.maxPayload:
            return None
        return {**frame, 'msg': bytes(frame['msg']) + bytes(self.maxPayload - len(frame['msg']))}


class UdpConnection(SocketConnection):
    """
    Simple Udp Connection
    """

    def __init__(self, ip, port, **kwargs):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._pending = bytearray()
        super().__init__(sock, ip, port, tx=Packer, rx=[Bytewise, HDRStuf, Unpacker], **kwargs)

    # [byte] upper limit of a datagram, stays below the MTU and the receive buffer of the ESP (1460)
    maxDatagram = 1400

    def _flush(self):
        """ send all collected frames as one datagram """
        if not self._pending or not self.connected:
            self._pending.clear()
            return
        data, self._pending = bytes(self._pending), bytearray()
        try:
            self.sock.sendall(data)
        except OSError as e:
            self._logger.error(f"cannot send data: {e}")

    @coroutine
    def _send(self):
        """
        collect the frames of one event loop iteration (e.g. all parameters and the start command
        of an experiment) and send them as one datagram, the bridge only buffers a few datagrams
        and loses the rest of a burst of single frames
        """
        while True:
            data = yield
            if len(self._pending) + len(data) > self.maxDatagram:
                self._flush()
            if not self._pending:
                QTimer.singleShot(0, self._flush)
            self._pending.extend(data)
