# -*- coding: utf-8 -*-
import os

import pytest

# run without a display if none is available
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolatedSettings(tmp_path, monkeypatch):
    """ keep tests from touching the user's real pywisp settings and working directory """
    from PyQt5.QtCore import QSettings
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "settings"))
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def cleanRegistry(monkeypatch):
    """ provide an empty registry for the duration of a test """
    import pywisp as pw
    monkeypatch.setattr(pw.registry, "_registry", pw.registry.Registry())
    return pw.registry._registry
