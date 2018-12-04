# -*- coding: utf-8 -*-
from .experimentModules import *
from .visualization import Visualizer

_registry = {}


def registerExperimentModule(expCls):
    """
    main hook to register a module in the pywisp framework
    :param moduleType:
    :param cls: class to be registered
    :return: None
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
    main hook to retrieve registered classes for a specific experiment module
    :param moduleType:
    :return:
    """
    return _registry.get(ExperimentModule, [])


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
    :return: visualizer class
    """
    return _registry.get(Visualizer, [])
