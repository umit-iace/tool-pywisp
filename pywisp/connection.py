# -*- coding: utf-8 -*-
"""
This module contains all classes and functions related to establishing a connection with a test rig.
"""

import logging
import socket
from abc import abstractmethod

import serial
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from .min import Packer, Unpacker, Frame, Bytewise, HDRStuf
from .utils import coroutine, pipe

__all__ = ["Connection", "UdpConnection", "TcpConnection", "SerialConnection", "IACEConnection"]


class ConnReader(QObject):
    """ Thread worker receiving connection data """
    err = pyqtSignal(str)

    def __init__(self, conn, rx):
        super().__init__()
        self.conn = conn
        self.stop = False
        self.rx = pipe(rx)

    def run(self):
        while not self.stop:
            try:
                data = self.conn._recv()
                self.rx.send(data)
            except TimeoutError:
                # intentionally empty
                pass
            except socket.timeout:
                # intentionally empty
                pass
            except Exception as e:
                if not self.stop:
                    self.err.emit(f"connection dropped: {repr(e)} / {e}")
                break

    def quit(self):
        self.stop = True


class Connection(QObject):
    """
    Base class for a connection, i.e. tcp or serial
    """
    received = pyqtSignal(Frame)
    finished = pyqtSignal()

    def __init__(self, rx, tx, *args, **kwargs):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tx = pipe([tx, self._send])
        thread = QThread()
        worker = ConnReader(self, [rx, self.emitter])
        worker.moveToThread(thread)
        worker.err.connect(self.workerror)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self.thread = thread
        self.worker = worker
        self.connected = False

    def workerror(self, err):
        self.worker.deleteLater()
        self.disconnect()
        self._logger.error(err)
        self.finished.emit()

    @coroutine
    def emitter(self):
        """
        send received frame to application
        """
        while True:
            id, payload = yield
            self.received.emit(Frame(id, payload))

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
            self.disconnect()

    def connect(self):
        """ establish the connection """
        if self._connect():
            self.thread.start()
            self.connected = True
            return True

    def disconnect(self):
        """ close the connection, stop worker and thread """
        self.connected = False
        self.worker.quit()
        self._disconnect()
        self.thread.quit()
        self.finished.emit()

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
        otherwise this will eat your cpu
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

    def __init__(self, port, baud):
        self.serial = serial.Serial(timeout=0.01)
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

    def __init__(self, socket, ip, port, timeout=0.01, **kwargs):
        self.ip = ip
        self.port = port
        self.sock = socket
        self.timeout = timeout
        super().__init__(**kwargs)

    def _connect(self):
        try:
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.ip, int(self.port)))
        except socket.error:
            self._logger.error("Connection to the server is not possible!")
            self.sock.close()
            return False
        return True

    def _disconnect(self):
        self.sock.close()

    def _recv(self):
        return self.sock.recv(512*4)

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

        @coroutine
        def Sender(sink):
            """ send 1 byte id + 80 byte payload """
            while True:
                id, data = (yield)
                sink.send(bytes([id]) + data + bytes(maxPayload - len(data)))

        @coroutine
        def Receiver(sink):
            """ receive 81 byte chunks -> (1 id + 80 payload) """
            data = []
            while True:
                data.extend((yield))
                while len(data) >= maxPayload + 1:
                    f, data = data[:maxPayload + 1], data[maxPayload + 1:]
                    sink.send((f[0], bytes(f[1:])))

        super().__init__(sock, ip, port, tx=Sender, rx=Receiver, **kwargs)


class UdpConnection(SocketConnection):
    """
    Simple Udp Connection
    """

    def __init__(self, ip, port, **kwargs):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        super().__init__(sock, ip, port, tx=Packer, rx=[Bytewise, HDRStuf, Unpacker], **kwargs)

class IACEConnection(UdpConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
