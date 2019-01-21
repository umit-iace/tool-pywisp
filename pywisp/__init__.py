# -*- coding: utf-8 -*-
import logging.config
import os

import matplotlib as mpl

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
__email__ = 'jens.wurm@umit.at'
__version__ = '1.0'

# configure logging
with open(get_resource("logging.yaml", ""), "r") as f:
    log_conf = yaml.load(f)

logging.config.dictConfig(log_conf)
