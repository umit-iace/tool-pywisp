import ast
import logging
import os
import subprocess
import sys
import tempfile

import pytest

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


@pytest.mark.parametrize("module", ["connectionManager", "export", "experiments", "session"])
def test_core_module_imports_no_widgets(module):
    """ the core runs headless, its modules do not import widgets, not even inside functions """
    path = os.path.join(os.path.dirname(pw.__file__), module + ".py")
    with open(path) as f:
        tree = ast.parse(f.read())
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    forbidden = [n for n in names if n in ("PyQt6.QtWidgets", "PyQt6.QtGui") or n.split(".")[0] == "widgets"]
    assert not forbidden


def test_session_runs_without_widgets():
    """ the package and a session only load QtCore, so they run under a QCoreApplication """
    out = runClean(
        "import sys\n"
        "from PyQt6.QtCore import QCoreApplication\n"
        "import pywisp\n"
        "app = QCoreApplication([])\n"
        "session = pywisp.Session()\n"
        "print(sorted(m for m in sys.modules if m.startswith(('PyQt6.QtWidgets', 'PyQt6.QtGui'))),\n"
        "      session.state, pywisp.MainGui.__name__, 'PyQt6.QtWidgets' in sys.modules)\n")
    assert out == "[] idle MainGui True"
