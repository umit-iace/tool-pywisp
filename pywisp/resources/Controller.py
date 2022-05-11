# -*- coding: utf-8 -*-
import time

from PyQt5.QtCore import QThread, pyqtSignal
import logging
from .inputs import devices, WIN

EVENT_ABB_LINUX = (
    # D-PAD, aka HAT
    ('Absolute-ABS_HAT0X', 'HX'),
    ('Absolute-ABS_HAT0Y', 'HY'),

    # A-PAD left
    ('Absolute-ABS_X', 'X'),
    ('Absolute-ABS_Y', 'Y'),

    # A-PAD right
    ('Absolute-ABS_Z', 'Z'),
    ('Absolute-ABS_RZ', 'RZ'),

    # Face Buttons
    ('Key-BTN_TRIGGER', 'N'),
    ('Key-BTN_THUMB', 'E'),
    ('Key-BTN_THUMB2', 'S'),
    ('Key-BTN_TOP', 'W'),

    # Shoulder buttons
    ('Key-BTN_BASE', 'THL'),
    ('Key-BTN_BASE2', 'THR'),
    ('Key-BTN_TOP2', 'TL'),
    ('Key-BTN_PINKIE', 'TR'),

    # Middle buttons
    ('Key-BTN_BASE3', 'Select'),
    ('Key-BTN_BASE4', 'Start'),
)

EVENT_ABB_WIN = (
    # D-PAD, aka HAT
    ('Absolute-ABS_HAT0X', 'HX'),
    ('Absolute-ABS_HAT0Y', 'HY'),

    # A-PAD left
    ('Absolute-ABS_X', 'X'),
    ('Absolute-ABS_Y', 'Y'),

    # A-PAD right
    ('Absolute-ABS_RX', 'RZ'),
    ('Absolute-ABS_RY', 'Z'),

    # Face Buttons
    ('Key-BTN_NORTH', 'N'),
    ('Key-BTN_EAST', 'E'),
    ('Key-BTN_SOUTH', 'S'),
    ('Key-BTN_WEST', 'W'),

    # Shoulder buttons
    # ('Absolute-ABS_Z', 'THL'), # TODO: diese beiden verursachen fehler, da ev_type absolute
    # ('Absolute-ABS_RZ', 'THR'),
    ('Key-BTN_TL', 'TL'),
    ('Key-BTN_TR', 'TR'),

    # Middle buttons
    ('Key-BTN_START', 'Select'),
    ('Key-BTN_SELECT', 'Start'),

    # joystick buttons
    # ('Key-BTN_THUMBL', 'L3'),
    # ('Key-BTN_THUMBR', 'R3'),
)

class GamePad(QThread):
    absHX = pyqtSignal(int)
    absHY = pyqtSignal(int)
    absX = pyqtSignal(int)
    absY = pyqtSignal(int)
    absZ = pyqtSignal(int)
    absRZ = pyqtSignal(int)
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

    def __init__(self):
        super().__init__()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.btnState = {}
        self.oldBtnState = {}
        self.absState = {}
        if WIN:
            self.abbrevs = dict(EVENT_ABB_WIN)
        else:
            self.abbrevs = dict(EVENT_ABB_LINUX)
        for key, value in self.abbrevs.items():
            if key.startswith('Absolute'):
                self.absState[value] = 127
            if key.startswith('Key'):
                self.btnState[value] = 0
                self.oldBtnState[value] = 0
        self.lastTime = 0
        self.runFlag = True

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
            print(event.ev_type, event.code)
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
        for key, value in self.absState.items():
            if self.absState[key] != 128:
                sig = getattr(self, 'abs' + key)
                sig.emit(1 if self.absState[key] > 127 else -1)

    def run(self):
        while self.runFlag:
            if WIN:
                devices.gamepads[0].__check_state()
            events = devices.gamepads[0]._do_iter()
            if events is not None:
                for event in events:
                    self.processEvent(event)

            curTime = int(time.time_ns() / 1000)
            if (curTime - self.lastTime) > 100000:
                self.lastTime = curTime
                self.outputAbsEvent()

            time.sleep(0.001)


def getController():
    """
    Detects if a gamepad is connected. Sets the input to gamepad if detected

    :return: gamepad or keyboard thread
    """
    if any(["GamePad" in des for des in [it[0] for it in [dir(dev) for dev in devices]]]):
        ctrl = GamePad()
        ctrl.setTerminationEnabled(True)
        ctrl.start()

        return ctrl
    else:
        return None
