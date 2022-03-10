# -*- coding: utf-8 -*-
"""
This module contains all classes and functions related to establishing a connection with a test rig.
"""

import logging
import socket
import time
from abc import abstractmethod

import serial
import serial.tools.list_ports
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from . import Min

__all__ = ["Connection", "UdpConnection", "TcpConnection", "SerialConnection"]

class Frame:
    def __init__(self, id, data):
        self.min_id = id    # backwards compatibility
        self.payload = data

class ConnReader(QObject):
    """ Thread worker """
    err = pyqtSignal(str)

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.stop = False

    def run(self):
        while not self.stop:
            try:
                self.conn._recv()
            except Exception:
                if not self.stop:
                    self.err.emit("connection dropped")
                break

    def quit(self):
        self.stop = True


class Connection(QObject):
    """
    Base class for a connection, i.e. tcp or serial
    """
    received = pyqtSignal(Frame)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.Min = Min(self._send(), self.emitter())
        thread = QThread()
        worker = ConnReader(self)
        worker.moveToThread(thread)
        worker.err.connect(self.workerror)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self.thread = thread
        self.worker = worker

    def workerror(self, err):
        self.worker.deleteLater()
        self.disconnect()
        self._logger.error(err)
        self.finished.emit()

    def emitter(self):
        """
        send received frame to application
        """
        while True:
            frame = yield
            self.received.emit(Frame(frame[0], frame[1]))

    def writeData(self, data):
        """
        push application data through min
        """
        try:
            self.Min.pack(data['id'], data['msg'])
        except Exception as e:
            self._logger.error(f"cannot send data: {e}")
            self.disconnect()

    def connect(self):
        """ establish the connection """
        if self._connect():
            self.thread.start()
            return True


    def disconnect(self):
        """ close the connection, stop worker and thread """
        self.worker.quit()
        self._disconnect()
        self.thread.quit()

    @abstractmethod
    def _connect(self):
        pass
    @abstractmethod
    def _disconnect(self):
        pass

    @abstractmethod
    def _recv(self):
        """
        receive data from connection.
        this runs in a threaded loop.
        make sure this actually takes some time (e.q. w/ socket timeouts)
        otherwise this will eat your cpu
        """
        pass

    @abstractmethod
    def _send(self):
        """
        write data out to the connection.
        coroutine.
        """
        pass
