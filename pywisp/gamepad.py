# -*- coding: utf-8 -*-
import ctypes
import logging
import os
import time

import yaml
from PyQt5.QtCore import QThread, pyqtSignal

from .inputs import WIN, rescan_devices
from .utils import getResource


class GamePad(QThread):
    absHX = pyqtSignal(float)
    absHY = pyqtSignal(float)
    absX = pyqtSignal(float)
    absY = pyqtSignal(float)
    absZ = pyqtSignal(float)
    absRZ = pyqtSignal(float)
    btnN = pyqtSignal()
    btnE = pyqtSignal()
    btnS = pyqtSignal()
    btnW = pyqtSignal()
    btnTHL = pyqtSignal()
    btnTL = pyqtSignal()
    btnTHR = pyqtSignal()
    btnTR = pyqtSignal()
    btnStart = pyqtSignal()
    btnSelect = pyqtSignal()

    def __init__(self, devices, indexOfController):
        super().__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.indexOfController = indexOfController

        self.devices = devices
        self.btnState = {}
        if WIN:
            self.stickResolution = 256 ** ctypes.sizeof(ctypes.c_short)
        else:
            self.stickResolution = 256 ** ctypes.sizeof(ctypes.c_ubyte)
        self.oldBtnState = {}
        self.absState = {}
        self.abbrevs = self.configureAbbrevs()
        for key, value in self.abbrevs.items():
            if key.startswith('Absolute'):
                self.absState[value] = 0
            if key.startswith('Key'):
                self.btnState[value] = 0
                self.oldBtnState[value] = 0
        self.lastTime = 0
        self.runFlag = True

    def getAbbrevs(self):
        return self.abbrevs

    def configureAbbrevs(self):
        # read config file
        runPath = os.getcwd()
        if WIN:
            fileName = os.path.join(runPath, 'gpWin.yaml')
            if os.path.exists(fileName):
                configFileName = fileName
            else:
                configFileName = getResource('gpPS4-WinDefault.yaml', '')
        else:
            fileName = os.path.join(runPath, 'gpLinux.yaml')
            if os.path.exists(fileName):
                configFileName = fileName
            else:
                configFileName = getResource('gpPS4-LinuxDefault.yaml', '')

        with open(configFileName, 'r') as f:
            configData = yaml.load(f, Loader=yaml.FullLoader)

        abbrevs = {}
        for item in configData.items():
            for key in item[1].items():
                abbrevs[key[1]] = key[0]
        return abbrevs

    def stop(self):
        self.runFlag = False
        self.quit()
        self.wait()

    def processEvent(self, event):
        if event.ev_type == 'Sync':
            return
        if event.ev_type == 'Misc':
            return
        key = event.ev_type + '-' + event.code
        try:
            abbv = self.abbrevs[key]
        except KeyError:
            self._logger.error("The event {} of type {} is not supported!".format(event.code, event.ev_type))
            print(event.ev_type + '-' + event.code)
            return

        if event.ev_type == 'Key':
            self.oldBtnState[abbv] = self.btnState[abbv]
            self.btnState[abbv] = event.state
            self.outputBtnEvent(event.ev_type, abbv)
        if event.ev_type == 'Absolute':
            self.absState[abbv] = event.state

    def outputBtnEvent(self, ev_type, abbv):
        if ev_type == 'Key':
            if self.btnState[abbv]:
                sig = getattr(self, 'btn' + abbv)
                sig.emit()
                return

    def outputAbsEvent(self):
        # sends number between -0.5 and 0.5 for abs values
        for key, value in self.absState.items():
            sig = getattr(self, 'abs' + key)
            if WIN:
                keyValue = round(self.absState[key] / self.stickResolution, 3)
            else:
                keyValue = round(self.absState[key] / self.stickResolution, 3) - 0.5
            sig.emit(keyValue)

    def run(self):
        while self.runFlag:
            if WIN:
                self.devices.gamepads[self.indexOfController].__check_state()
            try:
                events = self.devices.gamepads[self.indexOfController]._do_iter()
            except OSError:
                self.runFlag = False
                return

            if events is not None:
                for event in events:
                    self.processEvent(event)

            curTime = int(time.time_ns() / 1000)
            if (curTime - self.lastTime) > 100000:
                self.lastTime = curTime
                self.outputAbsEvent()

            time.sleep(0.001)


def getGamepadByIndex(devices, index):
    """
    Detects if a gamepad is connected. Sets the input to gamepad if detected

    :return: gamepad or keyboard thread
    """
    if devices.gamepads[index] is None:
        return None
    else:
        ctrl = GamePad(devices, index)
        ctrl.setTerminationEnabled(True)
        ctrl.start()
        return ctrl


def getAllGamepads():
    """
    Detects all connected gamepads.

    :return: list of detected Gamepads or "None" if empy
    """
    devices = rescan_devices()
    if any(["GamePad" in des for des in [it[0] for it in [dir(dev) for dev in devices]]]):
        return devices
    else:
        return None
