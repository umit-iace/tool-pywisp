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
from .gui import *
from .registry import *
from .utils import *
from .visualization import *
from .widgets.remote import MovableWidget as MovableWidget, registerRemoteWidget as registerRemoteWidget
