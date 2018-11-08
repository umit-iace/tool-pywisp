# -*- coding: utf-8 -*-
import logging.config

TABLEAU_COLORS = (
    ('blue', '#1f77b4'),
    ('orange', '#ff7f0e'),
    ('green', '#2ca02c'),
    ('red', '#d62728'),
    ('purple', '#9467bd'),
    ('brown', '#8c564b'),
    ('pink', '#e377c2'),
    ('gray', '#7f7f7f'),
    ('olive', '#bcbd22'),
    ('cyan', '#17becf'),
)

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
