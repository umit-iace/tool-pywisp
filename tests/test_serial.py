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
    form.connect()
    assert not form.isConnected


def test_invalid_baudrate(qtbot, cleanRegistry):
    pw.registerConnection(makeConnection(123456))
    form = pw.MainGui()
    qtbot.addWidget(form)
    with pytest.raises(ValueError):
        form.connect()
