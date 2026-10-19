# -*- coding: utf-8 -*-
# pyqtgraph uses the qt binding that has been imported first, so import PyQt6
# before anything pulls in pyqtgraph
from PyQt6 import QtCore  # noqa: F401

__author__ = 'IACE'
__email__ = 'jens.wurm@umit-tirol.at'
__version__ = '1.1.1'

from .min import *
from .connection import *
from .experimentModules import *
from .experiments import *
from .gui import *
from .registry import *
from .utils import *
from .visualization import *
