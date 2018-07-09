# -*- coding: utf-8 -*-
import logging
import time
import serial
import serial.tools.list_ports
from PyQt5 import QtCore


class SerialConnection(QtCore.QThread):
    """ A class for a serial interface connection implemented as a QThread

    """
    received = QtCore.pyqtSignal(object)

    def __init__(self, baud=115200):
        QtCore.QThread.__init__(self)
        self.serial = None
        self.baud = baud
        self.port = None
        self.isConnected = False

        self.moveToThread(self)

        self.timer = QtCore.QTimer()
        self.timer.moveToThread(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.readData)
        self.doRead = True

        # initialize logger
        self._logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        """ Starts the timer and thread

        """
        self.timer.start()
        self.exec_()

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
                self.serial = serial.Serial(self.port, self.baud, timeout=1000)
            except Exception as e:
                self._logger.error('{0}'.format(e))
                return False
            self.isConnected = True
            return True

    def disconnect(self):
        """ Close the serial interface connection

        """
        self.serial.close()
        self.isConnected = False

    def readData(self):
        """ Reads and emits the data, that comes over the serial interface.

        """
        while self.doRead:
            try:
                data = self.serial.readline().decode('ascii').strip()
                self.received.emit(data)
            except:
                continue

    def writeData(self, data):
        """ Writes the given data to the serial inferface.

        Parameters
        ----------
        data : str
            Readable string that will send over serial interface

        """
        self.doRead = False
        self.serial.write(data.encode('ascii'))
        time.sleep(0.1)
        self.doRead = True
