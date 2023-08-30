# -*- coding: utf-8 -*-
from .experimentModules import ExperimentModule
from .visualization import Visualizer
from .connection import Connection

class Registry(dict):
    def __init__(self):
        self[ExperimentModule] = {}
        self[Connection] = {}
        self[Visualizer] = {}

    def register(self, type, mod):
        if not issubclass(mod, type):
            raise TypeError(f"Cannot register {mod} as {type}!")
        if mod in self[type].values():
            raise ValueError(f'class {mod} already registered as {type}')
        self[type][mod.__name__] = mod

_registry = Registry()

def registerExperimentModule(expCls):
    """
    hook to register a module in the pywisp framework
    :param expCls: class to be registered
    """
    _registry.register(ExperimentModule, expCls)

def getRegisteredExperimentModules():
    """
    hook to retrieve registered experiment modules
    :return: list of experiment modules
    """
    return _registry[ExperimentModule]


def registerConnection(connCls):
    """
    hook to register a connection in the pywisp framework
    :param connCls: class to be registered
    """
    _registry.register(Connection, connCls)

def getRegisteredConnections():
    """
    hook to retrieve registered connections
    :return: list of connection classes
    """
    return _registry[Connection]


def registerVisualizer(visCls):
    """
    hook to register a visualizer for the experiment GUI
    :param visCls: class to be registered
    """
    _registry.register(Visualizer, visCls)

def getRegisteredVisualizers():
    """
    hook to retrieve registered visualizers
    :return: list of visualizer classes
    """
    return _registry[Visualizer]
