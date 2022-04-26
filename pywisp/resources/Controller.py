# -*- coding: utf-8 -*-
import time

from PyQt5.QtCore import QThread, pyqtSignal

from .inputs import devices

# TODO reconnect doesn't work very well
EVENT_ABB = (
    # D-PAD, aka HAT
    ('Absolute-ABS_HAT0X', 'HX'),
    ('Absolute-ABS_HAT0Y', 'HY'),

    # A-PAD
    ('Absolute-ABS_X', 'X'),
    ('Absolute-ABS_Y', 'Y'),

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
    ('Key-BTN_BASE3', 'SELECT'),
    ('Key-BTN_BASE4', 'START'),
)


class GamePad(QThread):
    absHX = pyqtSignal()
    absHY = pyqtSignal()
    absX = pyqtSignal()
    absY = pyqtSignal()
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
        self.btnState = {}
        self.oldBtnState = {}
        self.absState = {}
        self.abbrevs = dict(EVENT_ABB)
        for key, value in self.abbrevs.items():
            if key.startswith('Absolute'):
                self.absState[value] = 127
            if key.startswith('Key'):
                self.btnState[value] = 0
                self.oldBtnState[value] = 0
        self.lastTime = 0

    def stop(self):
        self.terminate()

    def processEvent(self, event):
        if event.ev_type == 'Sync':
            return
        if event.ev_type == 'Misc':
            return
        key = event.ev_type + '-' + event.code
        try:
            abbv = self.abbrevs[key]
        except KeyError:
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
            if self.absState[key] != 127:
                sig = getattr(self, 'abs' + key)
                sig.emit()

    def run(self):
        while True:
            events = devices.gamepads[0]._do_iter()
            if events is not None:
                for event in events:
                    self.processEvent(event)

            curTime = int(time.time_ns() / 1000)
            if (curTime - self.lastTime) > 100000:
                self.lastTime = curTime
                self.outputAbsEvent()


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
