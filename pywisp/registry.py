# -*- coding: utf-8 -*-
from .experimentModules import *
from .visualization import Visualizer
from .connection import Connection

_registry = {}


def registerExperimentModule(expCls):
    """
    hook to register a module in the pywisp framework
    :param expCls: class to be registered
    """
    if not issubclass(expCls, ExperimentModule):
        raise TypeError("Module must match type to be registered for! "
                        "{0} <> {1}".format(expCls, ExperimentModule))

    clsEntry = _registry.get(ExperimentModule, [])
    increment = (expCls, expCls.__name__)
    if increment in clsEntry:
        raise ValueError("class {0} already registered as experimentModule!"
                         "".format(expCls))

    clsEntry.append(increment)
    _registry[ExperimentModule] = clsEntry
    _registry[ExperimentModule.__name__] = clsEntry


def getRegisteredExperimentModules():
    """
    hook to retrieve registered experiment modules
    :return: list of experiment modules
    """
    return _registry.get(ExperimentModule, [])


def registerConnection(connCls):
    """
    hook to register a connection in the pywisp framework
    :param connCls: class to be registered
    """
    if not issubclass(connCls, Connection):
        raise TypeError("Module must match type to be registered for! "
                        "{0} <> {1}".format(connCls, Connection))

    clsEntry = _registry.get(Connection, [])
    increment = (connCls, connCls.__name__)
    if increment in clsEntry:
        raise ValueError("class {0} already registered as connection!"
                         "".format(connCls))

    clsEntry.append(increment)
    _registry[Connection] = clsEntry
    _registry[Connection.__name__] = clsEntry


def getRegisteredConnections():
    """
    hook to retrieve registered connections
    :return: list of connection classes
    """
    return _registry.get(Connection, [])


def registerVisualizer(visCls):
    """
    hook to register a visualizer for the experiment GUI
    :param visCls: class to be registered
    """
    if not issubclass(visCls, Visualizer):
        raise TypeError("Module must match type to be registered for! "
                        "{0} <> {1}".format(visCls, Visualizer))

    clsEntry = _registry.get(Visualizer, [])
    increment = (visCls, visCls.__name__)
    if increment in clsEntry:
        raise ValueError("class {0} already registered as visualizer!"
                         "".format(visCls))

    clsEntry.append(increment)
    _registry[Visualizer] = clsEntry
    _registry[Visualizer.__name__] = clsEntry


def getRegisteredVisualizers():
    """
    hook to retrieve registered visualizers
    :return: list of visualizer classes
    """
    return _registry.get(Visualizer, [])
