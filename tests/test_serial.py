# -*- coding: utf-8 -*-
import pytest

import pywisp as pw


def makeConnection(baud):
    class SerialTestConnection(pw.SerialConnection):
        settings = {
            "port": 'ttyIDK',
            "baud": baud,
        }

        def __init__(self):
            super().__init__(**self.settings)
    return SerialTestConnection


def test_valid_baudrate(qtbot, cleanRegistry):
    pw.registerConnection(makeConnection(1000000))
    form = pw.MainGui()
    qtbot.addWidget(form)
    # the port does not exist, so connecting fails gracefully
    form.connectRig()
    qtbot.waitUntil(lambda: not form._pendingConnections, timeout=5000)
    assert not form.isConnected
    assert form.actConnect.isEnabled()


def test_invalid_baudrate(qtbot, cleanRegistry):
    pw.registerConnection(makeConnection(123456))
    form = pw.MainGui()
    qtbot.addWidget(form)
    with pytest.raises(ValueError):
        form.connectRig()
