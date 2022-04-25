# -*- coding: utf-8 -*-
from PyQt5.QtCore import QThread, pyqtSignal
from inputs import get_gamepad, devices


# TODO reconnect doesn't work very well

class GamePad(QThread):
    btnTrigger = pyqtSignal()
    btnThumb = pyqtSignal()
    btnThumb2 = pyqtSignal()
    btnTop = pyqtSignal()

    def __init__(self):
        super().__init__()

    def stop(self):
        self.terminate()

    def run(self):
        while True:
            for event in get_gamepad():
                if event.ev_type == "Key":
                    if event.code == "BTN_TRIGGER":
                        if event.state:
                            self.btnTrigger.emit()
                    elif event.code == "BTN_THUMB":
                        if event.state:
                            self.btnThumb.emit()
                    elif event.code == "BTN_THUMB2":
                        if event.state:
                            self.btnThumb2.emit()
                    elif event.code == "BTN_TOP":
                        if event.state:
                            self.btnTop.emit()


def getController():
    """
    Detects if a gamepad is connected. Sets the input to gamepad if detected

    :return: gamepad or keyboard thread
    """
    msg = "{} as input device connected"
    if any(["GamePad" in des for des in [it[0] for it in [dir(dev) for dev in devices]]]):
        ctrl = GamePad()
        print(msg.format("gamepad"))
        ctrl.setTerminationEnabled(True)
        ctrl.start()
        return ctrl
    else:
        return None
