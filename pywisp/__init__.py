# -*- coding: utf-8 -*-
import os

# pyqtgraph uses the qt binding that has been imported first, so import PyQt5
# before anything pulls in pyqtgraph
from PyQt5 import QtCore  # noqa: F401

__author__ = 'IACE'
__email__ = 'jens.wurm@umit-tirol.at'
__version__ = '1.1.1'

# enable high dpi scaling, this only has an effect before the QApplication is
# created. Applications can override it by setting the variable themselves.
os.environ.setdefault('QT_AUTO_SCREEN_SCALE_FACTOR', "1")

from .min import *
from .connection import *
from .experimentModules import *
from .experiments import *
from .gui import *
from .registry import *
from .utils import *
from .visualization import *
