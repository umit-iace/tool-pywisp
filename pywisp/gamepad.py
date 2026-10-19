# -*- coding: utf-8 -*-
"""
Gamepad support based on the game controller api of SDL2.

SDL maps the inputs of most common controllers (PlayStation, Xbox, Switch, ...) onto a
standard layout on all platforms. The inputs of this layout are mapped onto the
abbreviations used for the remote widgets (``shortcut-Gp``), see :data:`DEFAULT_MAPPING`.
"""
import atexit
import logging
import os
import time
import warnings
from collections import namedtuple

import yaml
from PyQt5.QtCore import QThread, pyqtSignal

__all__ = ["Gamepad", "GamepadInfo", "getAllGamepads", "openGamepad", "DEFAULT_MAPPING"]

_logger = logging.getLogger("Gamepad")

#: abbreviations of the axes, they emit values in [-0.5, 0.5]
AXES = ('HX', 'HY', 'X', 'Y', 'Z', 'RZ')
#: abbreviations of the buttons, they emit when pressed
BUTTONS = ('N', 'E', 'S', 'W', 'THL', 'TL', 'THR', 'TR', 'Start', 'Select')

#: default mapping of the abbreviations onto the inputs of the SDL standard layout,
#: ``dpad-x`` and ``dpad-y`` turn the directional pad into an axis
DEFAULT_MAPPING = {
    'HX': 'dpad-x',
    'HY': 'dpad-y',
    'X': 'leftx',
    'Y': 'lefty',
    'Z': 'rightx',
    'RZ': 'righty',
    'N': 'y',
    'E': 'b',
    'S': 'a',
    'W': 'x',
    'TL': 'leftshoulder',
    'TR': 'rightshoulder',
    'THL': 'lefttrigger',
    'THR': 'righttrigger',
    'Select': 'back',
    'Start': 'start',
}

SDL_AXES = ('leftx', 'lefty', 'rightx', 'righty', 'lefttrigger', 'righttrigger')
SDL_BUTTONS = ('a', 'b', 'x', 'y', 'back', 'guide', 'start', 'leftstick', 'rightstick',
               'leftshoulder', 'rightshoulder', 'dpup', 'dpdown', 'dpleft', 'dpright',
               'misc1', 'paddle1', 'paddle2', 'paddle3', 'paddle4', 'touchpad')
DPAD = {'dpad-x': ('dpleft', 'dpright'), 'dpad-y': ('dpup', 'dpdown')}

# full range of an SDL axis
AXIS_RANGE = 65536
# triggers used as buttons count as pressed beyond half way
TRIGGER_THRESHOLD = 16384

# file in the working directory to change the mapping
MAPPING_FILE = 'gamepad.yaml'
# file in the working directory with additional SDL controller mappings
SDL_DB_FILE = 'gamecontrollerdb.txt'

GamepadInfo = namedtuple('GamepadInfo', ['id', 'name'])

_sdl = None


def _initSdl():
    """
    Load and initialize SDL on first use.

    :return: the sdl2 module or `None` if it is not available
    """
    global _sdl
    if _sdl is not None:
        return _sdl or None
    try:
        with warnings.catch_warnings():
            # pysdl2 announces the use of the binaries from pysdl2-dll
            warnings.simplefilter("ignore", UserWarning)
            import sdl2
    except (ImportError, RuntimeError) as e:
        _logger.error(f"Gamepads are not available, cannot load SDL2: {e}")
        _sdl = False
        return None

    # pywisp has no SDL window, so input must also be received in the background
    sdl2.SDL_SetHint(sdl2.SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, b"1")
    if sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_GAMECONTROLLER) != 0:
        _logger.error(f"Gamepads are not available: {sdl2.SDL_GetError().decode()}")
        _sdl = False
        return None
    atexit.register(sdl2.SDL_QuitSubSystem, sdl2.SDL_INIT_GAMECONTROLLER)

    if os.path.exists(SDL_DB_FILE):
        cnt = sdl2.SDL_GameControllerAddMappingsFromFile(SDL_DB_FILE.encode())
        if cnt < 0:
            _logger.error(f"Cannot read {SDL_DB_FILE}: {sdl2.SDL_GetError().decode()}")
        else:
            _logger.info(f"Loaded {cnt} controller mappings from {SDL_DB_FILE}")

    _sdl = sdl2
    return sdl2


def loadMapping(fileName=MAPPING_FILE):
    """
    Returns the mapping of the abbreviations onto SDL inputs.

    Entries of the given yaml file, mapping abbreviations to SDL input names, replace the defaults.
    """
    mapping = dict(DEFAULT_MAPPING)
    for old in ('gpLinux.yaml', 'gpWin.yaml'):
        if os.path.exists(old):
            _logger.warning(f"{old} is no longer supported, use {MAPPING_FILE} to change the gamepad mapping")
    if not os.path.exists(fileName):
        return mapping

    try:
        with open(fileName) as f:
            custom = yaml.safe_load(f) or {}
        if not isinstance(custom, dict):
            raise ValueError("must contain a mapping of abbreviations to SDL inputs")
    except (OSError, yaml.YAMLError, ValueError) as e:
        _logger.error(f"Cannot read {fileName}, using the default mapping: {e}")
        return mapping

    valid = SDL_AXES + SDL_BUTTONS + tuple(DPAD)
    for abbrev, name in custom.items():
        if abbrev not in DEFAULT_MAPPING:
            _logger.warning(f"{fileName}: unknown abbreviation '{abbrev}', available are {list(DEFAULT_MAPPING)}")
        elif name not in valid:
            _logger.warning(f"{fileName}: '{abbrev}' maps to unknown input '{name}', available are {list(valid)}")
        else:
            mapping[abbrev] = name
    return mapping


class SdlController:
    """ an opened SDL game controller """

    def __init__(self, deviceIndex):
        self.sdl = _initSdl()
        self._ctrl = self.sdl.SDL_GameControllerOpen(deviceIndex)
        if not self._ctrl:
            raise OSError(self.sdl.SDL_GetError().decode())
        self.name = (self.sdl.SDL_GameControllerName(self._ctrl) or b"").decode()
        self._axes = {name: self.sdl.SDL_GameControllerGetAxisFromString(name.encode()) for name in SDL_AXES}
        self._buttons = {name: self.sdl.SDL_GameControllerGetButtonFromString(name.encode()) for name in SDL_BUTTONS}

    def update(self):
        self.sdl.SDL_GameControllerUpdate()

    def attached(self):
        return bool(self.sdl.SDL_GameControllerGetAttached(self._ctrl))

    def axis(self, name):
        return self.sdl.SDL_GameControllerGetAxis(self._ctrl, self._axes[name])

    def button(self, name):
        return bool(self.sdl.SDL_GameControllerGetButton(self._ctrl, self._buttons[name]))

    def close(self):
        if self._ctrl:
            self.sdl.SDL_GameControllerClose(self._ctrl)
            self._ctrl = None


class Gamepad(QThread):
    """
    Polls a game controller and emits a signal for every pressed button.
    The values of all axes are emitted periodically.
    """
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

    # [s] interval to poll the buttons
    pollInterval = 0.001
    # [s] interval to emit the axis values
    axisInterval = 0.1

    def __init__(self, controller, mapping=None):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.controller = controller
        self.mapping = mapping or loadMapping()
        self._pressed = dict.fromkeys(BUTTONS, False)
        self._lastAxisTime = None
        self.runFlag = True

    @staticmethod
    def hasInput(abbrev):
        return abbrev in AXES or abbrev in BUTTONS

    @staticmethod
    def isAxis(abbrev):
        return abbrev in AXES

    def signal(self, abbrev):
        """ the signal emitted for the input with the given abbreviation """
        return getattr(self, ('abs' if self.isAxis(abbrev) else 'btn') + abbrev)

    def readButton(self, abbrev):
        name = self.mapping[abbrev]
        if name in SDL_AXES:
            return self.controller.axis(name) > TRIGGER_THRESHOLD
        if name in DPAD:
            return self.readAxis(abbrev) != 0
        return self.controller.button(name)

    def readAxis(self, abbrev):
        """ value of the axis in [-0.5, 0.5] """
        name = self.mapping[abbrev]
        if name in DPAD:
            low, high = DPAD[name]
            return 0.5 * (self.controller.button(high) - self.controller.button(low))
        if name in SDL_BUTTONS:
            return 0.5 if self.controller.button(name) else 0.0
        return round(self.controller.axis(name) / AXIS_RANGE, 3)

    def poll(self, now):
        """
        Reads the state of the controller and emits the signals.

        :param now: current time in seconds
        :return: `False` if the controller has been disconnected
        """
        self.controller.update()
        if not self.controller.attached():
            return False

        for abbrev in BUTTONS:
            pressed = self.readButton(abbrev)
            if pressed and not self._pressed[abbrev]:
                self.signal(abbrev).emit()
            self._pressed[abbrev] = pressed

        if self._lastAxisTime is None or now - self._lastAxisTime >= self.axisInterval:
            self._lastAxisTime = now
            for abbrev in AXES:
                self.signal(abbrev).emit(self.readAxis(abbrev))
        return True

    def run(self):
        try:
            while self.runFlag:
                if not self.poll(time.monotonic()):
                    self._logger.warning("Gamepad has been disconnected")
                    self.runFlag = False
                    break
                time.sleep(self.pollInterval)
        finally:
            self.controller.close()

    def stop(self):
        self.runFlag = False
        self.wait()


def getAllGamepads():
    """
    Detects all connected gamepads.

    :return: list of :class:`GamepadInfo`
    """
    sdl = _initSdl()
    if sdl is None:
        return []
    # detects newly connected devices
    sdl.SDL_GameControllerUpdate()
    pads = []
    for idx in range(sdl.SDL_NumJoysticks()):
        if not sdl.SDL_IsGameController(idx):
            name = (sdl.SDL_JoystickNameForIndex(idx) or b"").decode()
            _logger.warning(f"Joystick '{name}' is not supported, a mapping can be added to {SDL_DB_FILE}")
            continue
        name = (sdl.SDL_GameControllerNameForIndex(idx) or b"").decode()
        pads.append(GamepadInfo(sdl.SDL_JoystickGetDeviceInstanceID(idx), name))
    return pads


def openGamepad(gamepadId):
    """
    Opens a gamepad and starts polling it.

    :param gamepadId: id of the gamepad, see :class:`GamepadInfo`
    :return: the running :class:`Gamepad` or `None` if it cannot be opened
    """
    sdl = _initSdl()
    if sdl is None:
        return None
    indices = [idx for idx in range(sdl.SDL_NumJoysticks()) if sdl.SDL_JoystickGetDeviceInstanceID(idx) == gamepadId]
    if not indices:
        _logger.error("The selected gamepad is no longer connected")
        return None
    try:
        controller = SdlController(indices[0])
    except OSError as e:
        _logger.error(f"Cannot open the gamepad: {e}")
        return None

    pad = Gamepad(controller)
    pad.start()
    return pad
