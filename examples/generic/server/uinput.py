from threading import Thread
import time
from inputs import get_gamepad, get_key

try:
    import pygame
    pygame.init()
    pygame.joystick.init()
    pygameAvailable = True
    inputsAvailable = False
except ImportError:
    pygameAvailable = False
    try:
        import inputs
        inputsAvailable = True
    except ImportError:
        inputsAvailable = False


class PyGamePad(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.Key9 = 0
        self.Key10 = 0
        self.LStickX = 0
        self.LStickY = 0
        self.RStickX = 0
        self.RStickY = 0
        self.KeyBtnBase2 = 0
        self.KeyBtnPinkie = 0

        joystick_count = pygame.joystick.get_count()
        for i in range(joystick_count):
            joystick = pygame.joystick.Joystick(i)
            joystick.init()

    def run(self):

        while True:
            for event in pygame.event.get():
                print(event)
                if "button" in event.dict:
                    joystick = pygame.joystick.Joystick(event.dict["joy"])
                    if event.dict["button"] == 8:
                        self.Key9 = joystick.get_button(event.dict["button"])
                    elif event.dict["button"] == 5:
                        self.KeyBtnBase2 = joystick.get_button(event.dict["button"])
                    elif event.dict["button"] == 7:
                        self.KeyBtnPinkie = joystick.get_button(event.dict["button"])

                elif "axis" in event.dict:
                    print(event)
                    if event.dict["axis"] == 0:
                        self.LStickX = event.dict["value"]
                    elif event.dict["axis"] == 2:
                        self.RStickX = event.dict["value"]

    def getStickValue(self, value):
        return value if abs(value) > 0.08 else 0

    def control(self):
        roughControl = self.getStickValue(self.LStickX)
        sensitivControl = self.getStickValue(self.RStickX) * 0.4

        return roughControl + sensitivControl

    def cheat(self):
        return self.KeyBtnBase2 and self.KeyBtnPinkie

    def reset(self):
        return bool(self.Key9)

class GamePad(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.Key9 = 0
        self.Key10 = 0
        self.LStickX = 128
        self.LStickY = 128
        self.RStickX = 128
        self.RStickY = 128
        self.KeyBtnBase2 = 0
        self.KeyBtnPinkie = 0

    def run(self):
        while True:
            for event in get_gamepad():
                if event.ev_type == "Key":

                    if event.code == "BTN_BASE3":
                        self.Key9 = event.state
                    elif event.code == "BTN_BASE4":
                        self.Key10 = event.state
                    elif event.code == "BTN_BASE2":
                        self.KeyBtnBase2 = event.state
                    elif event.code == "BTN_PINKIE":
                        self.KeyBtnPinkie = event.state

                elif event.ev_type == "Absolute":

                    if event.code == "ABS_Z":
                        self.RStickX = event.state
                    elif event.code == "ABS_RZ":
                        self.RStickY = event.state
                    elif event.code == "ABS_X":
                        self.LStickX = event.state
                    elif event.code == "ABS_Y":
                        self.LStickY = event.state

    def getStickValue(self, value):
        res = ((value - 128) / 128)
        return res if abs(res) > 0.08 else 0

    def control(self):
        roughControl = self.getStickValue(self.LStickX)
        sensitivControl = self.getStickValue(self.RStickX) * 0.4

        return roughControl + sensitivControl

    def cheat(self):
        return self.KeyBtnBase2 and self.KeyBtnPinkie

    def reset(self):
        return bool(self.Key9)


class Keyboard(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.Left = 0
        self.Right = 0
        self.Enter = 0
        self.Backspace = 0

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
                    elif event.code == "KEY_BACKSPACE":
                        self.Backspace = event.state

    def control(self):
        return (self.Right - self.Left) / 2

    def cheat(self):
        return self.Enter == 1

    def reset(self):
        return self.Backspace == 1


def get_input_device():
    msg = "{} as input device connected"
    if pygameAvailable and pygame.joystick.get_count() > 0:
        input_ = PyGamePad()
        print(msg.format("gamepad (with pygame)"))

    elif inputsAvailable and len(inputs.devices.gamepads) > 0:
        input_ = GamePad()
        print(msg.format("gamepad (with inputs)"))

    else:
        input_ = Keyboard()
        print(msg.format("keyboard"))

    input_.start()

    return input_


if __name__ == "__main__":
    import time
    input_ = get_input_device()

    while True:
        time.sleep(1)
        print(input_.cheat(), input_.control(), input_.reset())
