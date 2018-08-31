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
        self.buffer = b''

        self.moveToThread(self)

        self.doRead = False

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

            self.readData()

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
        data = self.serial.readline()
        if len(data) > 0 and self.doRead:
            self.buffer += data
            if b'\r\n' in data:
                vals = self.buffer.decode('ascii').split('\r\n')
                for val in vals:
                    if val:
                        self.outputQueue.put(val.strip())
                self.buffer = b''

    def writeData(self, data):
        """ Writes the given data to the serial inferface.
        Parameters
        ----------
        data : str
            Readable string that will send over serial interface
        """
        self.serial.write(data.encode('ascii'))
        time.sleep(0.1)
