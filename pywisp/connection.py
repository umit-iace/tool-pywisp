# -*- coding: utf-8 -*-
import time

import logging
import serial
import serial.tools.list_ports
from PyQt5 import QtCore


class SerialConnection(QtCore.QThread):
    """ A class for a serial interface connection implemented as a QThread

    """

    def __init__(self,
                 inputQueue,
                 outputQueue,
                 port,
                 baud=115200):
        QtCore.QThread.__init__(self)
        self.serial = None
        self.baud = baud
        self.port = port
        self.isConnected = False
        self.inputQueue = inputQueue
        self.outputQueue = outputQueue

        self.moveToThread(self)

        self.doRead = False

        # error flags
        self.eC = 0
        self.eD = 0

        # initialize logger
        self._logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        """ Starts the timer and thread
        """
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

        while True and self.isConnected:
            if not self.inputQueue.empty():
                self.writeData(self.inputQueue.get())
            if self.serial.in_waiting > 2 and self.doRead:
                self.readData()

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
                self.serial = serial.Serial(self.port, self.baud, timeout=None)
            except Exception as e:
                self._logger.error('{0}'.format(e))
                return False
            self.isConnected = True
            return True

    def disconnect(self):
        """ Close the serial interface connection

        """
        self.isConnected = False
        time.sleep(1)
        while not self.inputQueue.empty():
            self.writeData(self.inputQueue.get())
        self.serial.close()
        self.serial = None

    def readData(self):
        """ Reads and emits the data, that comes over the serial interface.
        """
        self.serial.flush()
        data = self.serial.read_until(b'\r\n')

        # delete newline
        data = data[0:len(data) - 2]
        # extract checksum
        chcksum = data[len(data) - 2:len(data)]
        data = data[0:len(data) - 2]

        try:
            val = data.decode('ascii')
            self.eD = 0
        except UnicodeDecodeError:
            if self.eD == 0:
                self._logger.warning("Decoding Error. Throwing away dataset: " + str(data))
                self.eD = 1
            return
        # calculate checksum
        sm = 0
        for i in range(0, len(data)):
            sm = (sm + data[i]) % 0xffff
        if ~sm & 0xffff == int.from_bytes(chcksum, 'big'):
            self.outputQueue.put(val.strip())
            self.eC = 0
        elif self.eC == 0:
            self._logger.warning("Checksum failed. Throwing away dataset: " + str(val))
            self.eC = 1

    def writeData(self, data):
        """ Writes the given data to the serial inferface.
        Parameters
        ----------
        data : str
            Readable string that will send over serial interface
        """
        self.serial.write(data.encode('ascii'))
        time.sleep(0.1)
