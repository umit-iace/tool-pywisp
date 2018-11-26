# -*- coding: utf-8 -*-
from .experimentModules import *
from .visualization import Visualizer

_registry = {}


def registerModule(module_cls, module_type, cls, type_check=True):
    """
    Main hook to register a class (pywisp module) in the pywisp framework.
    """
    if type_check:
        if not issubclass(cls, module_type):
            raise TypeError("Module must match Type to be registered for "
                            "{0} <> {1}".format(cls, module_type))

    cls_entry = _registry.get(module_cls, {})
    entry = cls_entry.get(module_type, [])
    increment = (cls, cls.__name__)

    entry.append(increment)

    cls_entry[module_type] = entry
    _registry[module_cls] = cls_entry

    cls_entry[module_type.__name__] = entry
    _registry[module_cls.__name__] = cls_entry


def getRegisteredModules(module_cls, module_type):
    """
    Return registered classes of a module type for a specific module class.

    Returns:
        list: List of (obj, string) tuples.
    """
    return _registry.get(module_cls, {}).get(module_type, [])


def getModuleClassByName(module_cls, module_type, module_name):
    """
    return class object for given name
    :param module_name:
    :param module_type:
    :param module_cls:
    """
    return next((mod[0] for mod in getRegisteredModules(module_cls,
                                                        module_type)
                 if mod[1] == module_name), None)


def registerExperimentModule(moduleType, cls):
    """
    main hook to register a module in the pywisp framework
    :param moduleType:
    :param cls: class to be registered
    :return: None
    """
    if not issubclass(cls, ExperimentModule):
        raise TypeError("Only Experiment Modules can be registered!")

    registerModule(ExperimentModule, moduleType, cls, type_check=False)


def getRegisteredExperimentModules(moduleType):
    """
    main hook to retrieve registered classes for a specific experiment module
    :param moduleType:
    :return:
    """
    return getRegisteredModules(ExperimentModule, moduleType)


def getExperimentModuleClassByName(module_type, module_name):
    """
    Return the class of a certain experiment module given its registered name.

    Args:
        module_type (cls): Type of the module,
            see :py:func:`register_simulation_module` .
        module_name (str): name of the module.
    Returns:
    """
    return getModuleClassByName(ExperimentModule, module_type, module_name)


def registerVisualizer(vis_cls):
    """
    hook to register a visualizer for the experiment GUI
    :param vis_cls: class to be registered
    """
    if not issubclass(vis_cls, Visualizer):
        raise TypeError("Module must match type to be registered for! "
                        "{0} <> {1}".format(vis_cls, Visualizer))

    cls_entry = _registry.get(Visualizer, [])
    increment = (vis_cls, vis_cls.__name__)
    if increment in cls_entry:
        raise ValueError("class {0} already registered as visualizer!"
                         "".format(vis_cls))

    cls_entry.append(increment)
    _registry[Visualizer] = cls_entry
    _registry[Visualizer.__name__] = cls_entry


def getRegisteredVisualizers():
    """
    hook to retrieve registered visualizers
    :return: visualizer class
    """
    return _registry.get(Visualizer, [])
