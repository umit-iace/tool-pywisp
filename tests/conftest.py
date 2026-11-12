# -*- coding: utf-8 -*-
import os

import pytest

# always run headless, also if the shell sets a platform (e.g. xcb), so no windows or splash screen pop up
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(autouse=True)
def isolatedSettings(tmp_path, monkeypatch):
    """ keep tests from touching the user's real pywisp settings and working directory """
    from PyQt6.QtCore import QSettings
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "settings"))
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def cleanRegistry(monkeypatch):
    """ provide an empty registry for the duration of a test """
    import pywisp as pw
    monkeypatch.setattr(pw.registry, "_registry", pw.registry.Registry())
    return pw.registry._registry


@pytest.fixture
def sdl():
    import pywisp.gamepad as gp
    sdl = gp._initSdl()
    if sdl is None:
        pytest.skip("SDL2 is not available")
    return sdl


@pytest.fixture
def virtualPad(sdl):
    """ a virtual SDL game controller, its buttons and axes map onto the standard layout """
    idx = sdl.SDL_JoystickAttachVirtual(sdl.SDL_JOYSTICK_TYPE_GAMECONTROLLER, sdl.SDL_CONTROLLER_AXIS_MAX,
                                        sdl.SDL_CONTROLLER_BUTTON_MAX, 0)
    assert idx >= 0, sdl.SDL_GetError()
    joystick = sdl.SDL_JoystickOpen(idx)
    instanceId = sdl.SDL_JoystickInstanceID(joystick)

    class Virtual:
        id = instanceId

        def press(self, button, state=1):
            sdl.SDL_JoystickSetVirtualButton(joystick, button, state)

        def unplug(self):
            for i in range(sdl.SDL_NumJoysticks()):
                if sdl.SDL_JoystickGetDeviceInstanceID(i) == instanceId:
                    sdl.SDL_JoystickDetachVirtual(i)

    virtual = Virtual()
    yield virtual
    virtual.unplug()
    sdl.SDL_JoystickClose(joystick)
