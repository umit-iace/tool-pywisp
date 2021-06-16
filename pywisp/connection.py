# -*- coding: utf-8 -*-
"""
This module contains all classes and functions related to establishing a connection with a test rig.
"""

import logging
import socket
import struct
import time
from abc import abstractmethod

import serial
import serial.tools.list_ports
from PyQt5 import QtCore

from . import MINSerial, MINFrame

__all__ = ["Connection", "TcpConnection", "SerialConnection"]


class Connection(object):
    """
    Base class for a connection, i.e. tcp or serial
    """
    received = QtCore.pyqtSignal(object)

    def __init__(self):
        self.isConnected = False
        self._logger = logging.getLogger(self.__class__.__name__)
        self.doRead = False

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def clear(self):
        pass

    @abstractmethod
    def readData(self, frames):
        pass

    @abstractmethod
    def writeData(self, data):
        pass


class SerialConnection(Connection, QtCore.QThread):
    """
    A connection derived class for a serial interface connection implemented as a QThread
    """

    def __init__(self,
                 port,
                 baud,
                 withTransport=True):
        super(SerialConnection, self).__init__()
        QtCore.QThread.__init__(self)

        self.min = None
        self.baud = baud
        self.port = port
        self.withTransport = withTransport
        self.moveToThread(self)

    def run(self):
        """
        Endless loop of the thread
        """
        while True and self.isConnected:
            try:
                frames = self.min.poll()
            except:
                self._logger.error('run: No Connection')
                self.isConnected = False
                self.min = None
                return

            if frames and self.doRead:
                self.readData(frames)
            else:
                time.sleep(0.001)

    def connect(self):
        """
        Checks if the given port is available and instantiates the min protocol
        :return: True if successful connected, False otherwise.
        """
        ports = [
            p.device
            for p in serial.tools.list_ports.comports()
        ]
        if self.port not in ports:
            self.isConnected = False
            return False
        else:
            try:
                self.min = MINSerial(self.port, self.baud, withTransport=self.withTransport)
            except Exception as e:
                self._logger.error('{0}'.format(e))
                return False
            self.isConnected = True
            return True

    def disconnect(self):
        """
        Closes the min protocol and resets the connection
        """
        time.sleep(1)
        self.isConnected = False
        self._reset()
        if self.min:
            self.min.close()
            del self.min

    def clear(self):
        self._reset(False)

    def _reset(self, reset=True):
        if reset and self.min is not None:
            if self.withTransport:
                self.min.transport_reset()
            else:
                self.min.reset()
        time.sleep(0.1)

    def readData(self, frames):
        """
        Reads and emits the data frame that comes over the serial interface.
        :param frames: min frame from the other side
        """
        for frame in frames:
            self.received.emit(frame)

    def writeData(self, data):
        """
        Writes the given data frame to the min queue
        :param data: dictionary that includes the min id and payload
        """
        if self.min:
            if self.withTransport:
                self.min.queue_frame(min_id=data['id'], payload=data['msg'])
            else:
                self.min.send_frame(min_id=data['id'], payload=data['msg'])


class TcpConnection(Connection, QtCore.QThread):
    """
    A connection derived Class for a tcp client implemented as a QThread, which connects to a server
    """
    def __init__(self,
                 ip,
                 port,
                 payloadLen=80,
                 timeout=0.01):
        super(TcpConnection, self).__init__()
        QtCore.QThread.__init__(self)

        self.ip = ip
        self.port = port
        self.sock = None
        self.payloadLen = payloadLen
        self.timeout = timeout
        self.moveToThread(self)

    def disconnect(self):
        self.isConnected = False
        time.sleep(1)
        if self.sock is not None:
            self.sock.close()
        self._reset()

    def clear(self):
        self._reset()

    def _reset(self, ):
        pass

    def connect(self):
        """
        Checks if the given port is available and instantiates the socket connection
        :return: True if successful connected, False otherwise.
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.ip, int(self.port)))
        except socket.error:
            self._logger.error("Connection to the server is not possible!")
            self.sock.close()
            self.sock = None
            return False
        self.isConnected = True
        self.sock.settimeout(self.timeout)
        return True

    def getIP(self):
        """
        Gets the IP address of host and returns it
        :return: the IP address
        """
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip

    def run(self):
        """
        Endless loop of the thread
        """
        while self.isConnected:
            if self.doRead:
                self.readData(None)
            else:
                time.sleep(self.timeout)

    def readData(self, frames):
        """
        Reads a data frame from the socket connection, builds a min frame and emits it.
        :param frames: nothing
        """
        try:
            data = self.sock.recv(self.payloadLen + 1)
            if data and data != b'':
                if len(data) != self.payloadLen + 1:
                    self._logger.error(
                        "Length of data {} differs from payload length {}!".format(len(data), self.payloadLen + 1))
                else:
                    frame = MINFrame(data[0], data[1:], 0, False)
                    self.received.emit(frame)
        except socket.timeout:
            # if nothing is to read, get on
            pass
        except socket.error as e:
            self._logger.error("Reading from host not possible! {}".format(e))
            self.isConnected = False

    def writeData(self, data):
        """
        Writes a data frame to the socket connection
        :param data: data frame to be sent
        """
        try:
            outputData = struct.pack('>B', data['id']) + data['msg']
            if len(outputData) < self.payloadLen + 1:
                for i in range(self.payloadLen + 1 - len(outputData)):
                    outputData += b'\x00'
            self.sock.send(outputData)
        except Exception as e:
            self._logger.error("Writing to host not possible! {}".format(e))
            self.isConnected = False
