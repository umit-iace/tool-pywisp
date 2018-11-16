# -*- coding: utf-8 -*-
import logging
import serial
import serial.tools.list_ports
import socket
import time
from PyQt5 import QtCore
import struct

from . import MINTransportSerial

class Connection(QtCore.QThread):
    """ Base class for serial and tcp connection

    """
    def __init__(self, inputQueue, outputQueue, port):
        QtCore.QThread.__init__(self)
        self.isConnected = False
        self.port = port
        self.inputQueue = inputQueue
        self.outputQueue = outputQueue
        self._logger = logging.getLogger(self.__class__.__name__)


class SerialConnection(Connection):
    """ A class for a serial interface connection implemented as a QThread

    """

    def __init__(self,
                 inputQueue,
                 outputQueue,
                 port,
                 baud=115200):
        self.min = None
        self.baud = baud
        super(SerialConnection, self).__init__(inputQueue, outputQueue, port)

        self.doRead = False

    def connect(self):
        """ Checks of an arduino port is avaiable and connect to these one.

        Returns
        -------
        bool
            True if successful connected, False otherwise.
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
                self.min = MINTransportSerial(self.port, self.baud)
            except Exception as e:
                self._logger.error('{0}'.format(e))
                return False
            self.isConnected = True
            return True

    def run(self):
        """ Starts the timer and thread
        """
        while True and self.isConnected:
            frames = self.min.poll()
            if not self.inputQueue.empty():
                self.writeData(self.inputQueue.get())
            if frames and self.doRead:
                self.readData(frames)
            time.sleep(0.001)

    def disconnect(self):
        """ Close the serial interface connection

        """
        self.isConnected = False
        time.sleep(1)
        while not self.inputQueue.empty():
            self.writeData(self.inputQueue.get())

        self.min.transport_reset()
        del self.min

    def readData(self, frames):
        """ Reads and emits the data, that comes over the serial interface.
        """
        for frame in frames:
            self.outputQueue.put(frame)

    def writeData(self, data):
        """ Writes the given data to the serial inferface.
        Parameters
        ----------
        data : dict
            Readable string that will send over serial interface
        """
        self.min.queue_frame(min_id=data['id'], payload=data['msg'])

class TcpConnection(Connection):
    """ A Class for a tcp client which connects a server

    """
    def __init__(self,
                 inputQueue,
                 outputQueue,
                 port,
                 ipadr):
        self.client_ip = ipadr
        self.sock = None
        super(TcpConnection, self).__init__(inputQueue, outputQueue, port)
        self.controlword = 0x0000

    def disconnect(self):
        self.isConnected = False
        time.sleep(1)
        while not self.inputQueue.empty():
            self.writeData(self.inputQueue.get())
        if not (self.sock == None):
            self.sock.close()

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.client_ip, self.port))
        except socket.error:
            self._logger.error("Verbinden zum Server nicht möglich!")
            self.sock.close()
            self.sock = None
            return False
        self.isConnected = True
        return True

    def getIP():
        """
        get the IP adress of host and return it
        """
        hostname = socket.gethostname()
        own_ip = socket.gethostbyname(hostname)
        return own_ip

    def run(self):
        """ Starts the timer and thread
        """
        while True and self.isConnected:
            if not self.inputQueue.empty():
                self.writeData(self.inputQueue.get())
            self.readData()
            time.sleep(0.001)

    def readData(self):
        try:
            inputdata = self.sock.recv(18)
            if inputdata == b'\x32':
                self.isConnected = False
                self.writeData({'id': 1, 'msg': b'\x32'})
            elif inputdata == b'':
                pass
            else:
                self.outputQueue.put(inputdata)
        except:
            self._logger.error("Lesen vom Host nicht möglich!")
            self.isConnected = False

    def writeData(self, data):
        self.controlword = (self.controlword & 0xFF0F) + (data['id'] << 4)
        if (data['id'] == 1) and (data['msg'] == 1):
            # start experiment
            self.controlword = (self.controlword & 0xFCFF) + (1 << 8)
        elif (data['id'] == 1) and (data['msg'] == 0):
            # stop experiment
            self.controlword = (self.controlword & 0xFCFF) + (1 << 9)
        elif (data['id'] == 40) and (data['msg'] == 3):
            # start trajectory
            self.controlword = (self.controlword & 0xF3FF) + (3 << 10)
        elif (data['id'] == 40) and (data['msg'] == 0):
            # stop trajectory
            self.controlword = (self.controlword & 0xF3FF)
        elif (data['id'] == 50) and (data['msg'] == 1):
            # start controller
            self.controlword = (self.controlword & 0xEFFF) + (1 << 12)
        elif (data['id'] == 50) and (data['msg'] == 0):
            # stop controller
            self.controlword = (self.controlword & 0xEFFF)
        try:
            self.sock.send(struct.pack('>H', self.controlword) + data['msg'])
        except:
            self._logger.error("Schreiben an Host nicht möglich!")
            self.isConnected = False


# TODO create a communication protocoll to start/end experiments and to close conn

# TODO -> testbench.py, trajectory.py, controller.py
