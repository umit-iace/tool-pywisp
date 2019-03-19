# -*- coding: utf-8 -*-
from threading import Thread
from inputs import get_gamepad, get_key, devices


class GamePad(Thread):
    """
    Implementation of a gamepad control as a separate thread
    """
    def __init__(self):
        Thread.__init__(self)
        self.Key9 = 0
        self.Key10 = 0
        self.LStickX = 0
        self.LStickY = 0
        self.RStickX = 0
        self.RStickY = 0

    def run(self):
        while True:
            for event in get_gamepad():
                if event.ev_type == "Key":

                    if event.code == "BTN_BASE3":
                        self.Key9 = event.state
                    elif event.code == "BTN_BASE4":
                        self.Key10 = event.state

                elif event.ev_type == "Absolute":

                    if event.code == "ABS_Z":
                        self.RStickX = event.state
                    elif event.code == "ABS_RZ":
                        self.RStickY = event.state
                    elif event.code == "ABS_X":
                        self.LStickX = event.state
                    elif event.code == "ABS_Y":
                        self.LStickY = event.state

    def control(self):
        gain = 10
        return ((self.LStickX - 128) / 128) * gain

    def reset(self):
        return bool(self.Key9)


class Keyboard(Thread):
    """
    Implementation of a keyboard control as a separate thread
    """
    def __init__(self):
        Thread.__init__(self)
        self.Left = 0
        self.Right = 0
        self.Enter = 0

    def run(self):
        while True:
            for event in get_key():
                if event.ev_type == "Key":

                    if event.code == "KEY_LEFT":
                        self.Left = event.state
                    elif event.code == "KEY_RIGHT":
                        self.Right = event.state
                    elif event.code == "KEY_ENTER":
                        self.Enter = event.state

    def control(self):
        gain = 10
        return (self.Right - self.Left) / 2 * gain

    def reset(self):
        return self.Enter


def get_input_device():
    """
    Detects if an gamepad is connected. Sets the input to gamepad if detected or otherwise to keboard

    :return: gamepad or keyboard thread
    """
    msg = "{} as input device connected"
    if any(["GamePad" in des for des in [it[0] for it in [dir(dev) for dev in devices]]]):
        input_ = GamePad()
        print(msg.format("gamepad"))

    else:
        input_ = Keyboard()
        print(msg.format("keyboard"))

    input_.start()

    return input_
