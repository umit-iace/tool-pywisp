# -*- coding: utf-8 -*-
import logging.config

from .min import *
from .connection import *
from .experimentModules import *
from .experiments import *
from .experiments import *
from .gui import *
from .registry import *
from .utils import *
from .visualization import *

# configure logging
with open(get_resource("logging.yaml", ""), "r") as f:
    log_conf = yaml.load(f)

logging.config.dictConfig(log_conf)
