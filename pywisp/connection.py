# -*- coding: utf-8 -*-
import logging
import time

import serial
import serial.tools.list_ports
from PyQt5 import QtCore


class SerialConnection(QtCore.QThread):
    """ A class for a serial interface connection implemented as a QThread

    """
    def __init__(self,
                 inputQueue,
                 outputQueue,
                 baud=115200):
        QtCore.QThread.__init__(self)
        self.serial = None
        self.baud = baud
        self.port = None
        self.isConnected = False
        self.inputQueue = inputQueue
        self.outputQueue = outputQueue

        self.moveToThread(self)

        # initialize logger
        self._logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        self.serial.flushInput()

        while True and self.isConnected:
            # look for incoming request
            if not self.inputQueue.empty():
                self.writeSerial(self.inputQueue.get())

            # look for incoming serial data
            if self.serial.in_waiting > 0:
                data = self.readSerial()
                self.outputQueue.put(data)

    def connect(self):
        """ Checks of an arduino port is avaiable and connect to these one.

        Returns
        -------
        bool
            True if successful connected, False otherwise.
        """
        arduino_ports = [
            p.device
            for p in serial.tools.list_ports.comports()
            if 'Arduino' in p.description
        ]
        if not arduino_ports:
            self.isConnected = False
            return False
        else:
            self.port = arduino_ports[0]
            try:
                self.serial = serial.Serial(self.port, self.baud, timeout=0)
            except Exception as e:
                self._logger.error('{0}'.format(e))
                return False
            self.isConnected = True
            return True

    def disconnect(self):
        """ Close the serial interface connection

        """
        self.serial.close()
        self.serial = None
        self.isConnected = False

    def readData(self):
        """ Reads and emits the data, that comes over the serial interface.

        """
        return self.serial.readline().decode('ascii').strip()

    def writeData(self, data):
        """ Writes the given data to the serial inferface.

        Parameters
        ----------
        data : str
            Readable string that will send over serial interface

        """
        self.serial.write(data.encode('ascii'))
        time.sleep(0.1)
