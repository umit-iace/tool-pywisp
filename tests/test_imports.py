import logging
import os
import subprocess
import sys
import tempfile

import pywisp as pw


def runClean(code):
    """ run code in a fresh interpreter, pytest itself configures logging """
    env = dict(os.environ)
    env.pop('PYQTGRAPH_QT_LIB', None)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    with tempfile.TemporaryDirectory() as tmp:
        # keep the settings of the gui away from the user's config
        env['XDG_CONFIG_HOME'] = env['HOME'] = tmp
        res = subprocess.run([sys.executable, '-c', code], env=env, cwd=tmp,
                             capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    return res.stdout.strip().splitlines()[-1]


def test_import_has_no_side_effects():
    out = runClean(
        "import logging, os, sys\n"
        "import pywisp\n"
        "import pyqtgraph.Qt\n"
        "print(len(logging.getLogger().handlers), 'matplotlib.pyplot' in sys.modules,\n"
        "      os.environ.get('PYQTGRAPH_QT_LIB'), pyqtgraph.Qt.QT_LIB)\n")
    assert out == "0 False None PyQt6"


def test_gui_configures_logging():
    out = runClean(
        "import logging\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "import pywisp\n"
        "app = QApplication([])\n"
        "gui = pywisp.MainGui()\n"
        "root = logging.getLogger()\n"
        "print(root.level, sorted(type(h).__name__ for h in root.handlers))\n")
    assert out == "20 ['PlainTextLogger', 'StreamHandler']"


def test_gui_keeps_application_logging():
    out = runClean(
        "import logging\n"
        "logging.basicConfig(level=logging.DEBUG, filename='/dev/null')\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "import pywisp\n"
        "app = QApplication([])\n"
        "gui = pywisp.MainGui()\n"
        "root = logging.getLogger()\n"
        "print(root.level, sorted(type(h).__name__ for h in root.handlers))\n")
    assert out == "10 ['FileHandler', 'PlainTextLogger']"


def test_setup_logging_force(monkeypatch):
    root = logging.getLogger()
    monkeypatch.setattr(root, 'handlers', [logging.NullHandler()])
    monkeypatch.setattr(root, 'level', logging.WARNING)
    pw.setupLogging()
    assert root.level == logging.WARNING
    pw.setupLogging(force=True)
    assert root.level == logging.INFO
    assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
