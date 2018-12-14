# -*- coding: utf-8 -*-
import logging
import serial
import serial.tools.list_ports
import socket
import time
from PyQt5 import QtCore
import struct

from . import MINTransportSerial, MINFrame

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

    def run(self):
        """ Starts the timer and thread
        """
        while True and self.isConnected:
            frames = self.min.poll()
            if not self.inputQueue.empty():
                self.writeData(self.inputQueue.get())
            if frames and self.doRead:
                self.readData(frames)
            time.sleep(0.01)

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

    def disconnect(self):
        """ Close the serial interface connection

        """
        time.sleep(1)
        self.isConnected = False
        self._reset()
        self.min.close()
        del self.min

    def clear(self):
        self._reset(False)

    def _reset(self, reset=True):
        while not self.inputQueue.empty():
            self.writeData(self.inputQueue.get())

        if reset:
            self.min.transport_reset()
        time.sleep(0.1)
        self.min.poll()

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
    payloadLen = 80
    def __init__(self,
                 inputQueue,
                 outputQueue,
                 port,
                 ipadr):
        self.client_ip = ipadr
        self.sock = None
        super(TcpConnection, self).__init__(inputQueue, outputQueue, port)

    def disconnect(self):
        self.isConnected = False
        time.sleep(1)
        while not self.inputQueue.empty():
            self.writeData(self.inputQueue.get())
        if not (self.sock == None):
            self.sock.close()
        self._reset()

    def clear(self):
        self._reset()

    def _reset(self,):
        while not self.inputQueue.empty():
            self.writeData(self.inputQueue.get())
        time.sleep(0.1)

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
        self.sock.settimeout(0.001)
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
            self.readData()
            if not self.inputQueue.empty():
                self.writeData(self.inputQueue.get())
            time.sleep(0.001)

    def readData(self):
        try:
            data = self.sock.recv(self.payloadLen + 1)
            if data == b'\x32': # wut is this
                self.isConnected = False
                self.writeData({'id': 1, 'msg': b'\x32'})
            elif data == b'':
                pass
            if data:
                if len(data) != self.payloadLen + 1:
                    print('wooooah not good')
                frame = MINFrame(data[0],data[1:],0,0)
                # print("Recv: ", data)
                self.outputQueue.put(frame)
        except socket.timeout:
            # if nothing is to read, get on
            pass
        except socket.error:
            self._logger.error("Lesen vom Host nicht möglich!")
            self.isConnected = False

    def writeData(self, data):
        try:
            outputdata = struct.pack('>B', data['id']) + data['msg']
            if (len(outputdata) < self.payloadLen + 1):
                for i in range(self.payloadLen + 1 - len(outputdata)):
                    outputdata += b'\x00'
            self.sock.send(outputdata)
            # print("send: ", outputdata, " with ", data['id'], " and ", data['msg'])
        except:
            self._logger.error("Schreiben an Host nicht möglich!")
            self.isConnected = False
