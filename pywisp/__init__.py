# -*- coding: utf-8 -*-
# pyqtgraph uses the qt binding that has been imported first, so import PyQt6
# before anything pulls in pyqtgraph
from PyQt6 import QtCore  # noqa: F401

__author__ = 'IACE'
__email__ = 'jens.wurm@umit-tirol.at'
__version__ = '1.1.1'
#: tool-libs version (tag or branch) the rig software has to use, the examples are built with it
TOOL_LIBS_VERSION = 'feature/tests'

from .min import *
from .connection import *
from .experimentModules import *
from .experiments import *
from .registry import *
from .utils import *
from .session import *

# the widgets need QtWidgets, they are imported on first use, so the core runs headless under a QCoreApplication
_LAZY = {name: '.widgets.experimentview'
         for name in ("ExperimentModel", "PropertyItem", "PropertyDelegate", "ExperimentView")}
_LAZY.update({name: '.visualization' for name in ("Visualizer", "MplVisualizer", "VtkVisualizer")})
_LAZY.update(MainGui='.gui', MovableWidget='.widgets.remote', registerRemoteWidget='.widgets.remote')

__all__ = [name for name in globals() if not name.startswith('_')] + list(_LAZY)


def __getattr__(name):
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(_LAZY[name], __name__), name)
    globals()[name] = value
    return value
