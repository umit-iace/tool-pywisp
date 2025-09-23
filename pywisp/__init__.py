# -*- coding: utf-8 -*-
import logging.config
import matplotlib as mpl
import os

# make everybody use qt5
mpl.use('Qt5Agg')
os.environ["PYQTGRAPH_QT_LIB"] = "PyQt5"
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = "1"

from .min import *
from .connection import *
from .experimentModules import *
from .experiments import *
from .experiments import *
from .gui import *
from .registry import *
from .utils import *
from .visualization import *

__author__ = 'IACE'
__email__ = 'jens.wurm@umit-tirol.at'
__version__ = '1.1.1'

# configure logging
with open(getResource("logging.yaml", ""), "r") as f:
    log_conf = yaml.load(f, Loader=Loader)

logging.config.dictConfig(log_conf)

# go to correct directory
import sys
if (dir := os.path.dirname(sys.argv[-1])):
    os.chdir(dir)
