# -*- coding: utf-8 -*-
import logging
import serial
import serial.tools.list_ports
import time
from PyQt5 import QtCore

from min_WIP.min_comm_host.min import MINTransportSerial


class SerialConnection(QtCore.QThread):
    """ A class for a serial interface connection implemented as a QThread

    """

    def __init__(self,
                 inputQueue,
                 outputQueue,
                 port,
                 baud=115200):
        QtCore.QThread.__init__(self)
        self.min = None
        self.baud = baud
        self.port = port

        self.isConnected = False
        self.inputQueue = inputQueue
        self.outputQueue = outputQueue

        self.moveToThread(self)

        self.doRead = False

        # initialize logger
        self._logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        """ Starts the timer and thread
        """
        while True and self.isConnected:
            frames = self.min.poll()
            if not self.inputQueue.empty():
                self.writeData(self.inputQueue.get())
            if frames and self.doRead:
                self.readData(frames)

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
