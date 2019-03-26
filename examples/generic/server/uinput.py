from threading import Thread
from inputs import get_gamepad, get_key, devices


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
        return self.Enter == 2

    def reset(self):
        return self.Backspace == 2


def get_input_device():
    msg = "{} as input device connected"
    if any(["GamePad" in des for des in [it[0] for it in [dir(dev) for dev in devices]]]):
        input_ = GamePad()
        print(msg.format("gamepad"))

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
        print(input_.control())
