# -*- coding: utf-8 -*-
"""
General helpers: coroutine pipes, resources and packing of data arrays.
"""
import importlib
import logging
import logging.config
import os
import struct
import warnings

import yaml

__all__ = ["createDir", "getResource", "setupLogging", "packArrayToFrame", "coroutine", "pipe"]


def flatten(lst):
    """ flatten an arbitrarily nested list """
    ret = []
    if isinstance(lst, list):
        for item in lst:
            if isinstance(item, list):
                ret.extend(flatten(item))
            else:
                ret.append(item)
        return ret
    else:
        return lst


def coroutine(func):
    """ wrapper for starting coroutine upon creation """

    def start(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr

    return start


def pipe(coros):
    """ start a pipe of coroutines """
    coros = flatten(coros)

    ret = coros[-1]()
    for coro in reversed(coros[:-1]):
        ret = coro(ret)
    return ret


def createDir(dirName):
    """
    Checks if directory exists and create the directory if not.
    :param dirName: directory name
    :return: path of directory
    """
    path = os.path.join(os.getcwd(), dirName)
    os.makedirs(path, exist_ok=True)
    return path


def getResource(resName, resType="icons"):
    """
    Build absolute path to specified resource within the package
    :param resName: name of the ressource
    :param resType: sub directory
    :return: path to resource
    """
    ownPath = os.path.dirname(__file__)
    resourcePath = os.path.abspath(os.path.join(ownPath, "resources", resType))
    return os.path.join(resourcePath, resName)


def setupLogging(force=False):
    """
    Configure the logging with the defaults of pywisp (console output, level INFO).

    This is done by :class:`pywisp.MainGui`, if the application has not configured
    logging itself.

    :param force: apply the configuration even if the root logger already has handlers
    """
    if logging.getLogger().handlers and not force:
        return
    with open(getResource("logging.yaml", ""), "r") as f:
        logging.config.dictConfig(yaml.safe_load(f))


def getFormattedStructString(dataLenFloat: int, dataLenInt: int , lenFloat: int) -> str:
    """
    Returns a format string for the struct package by given float and integer length and
    count of floats.

    :param dataLenFloat: length of float datatype
    :type dataLenFloat: int
    :param dataLenInt: length of integer datatype
    :type dataLenInt: int
    :param lenFloat: length of float data
    :type lenFloat: int

    :return: Struct-type format string that encodes the reuqired data fields.
    """
    if dataLenFloat == 4:
        floatStr = 'f'
    elif dataLenFloat == 8:
        floatStr = 'd'
    else:
        floatStr = 'f'

    if dataLenInt == 1:
        intStr = 'B'
    elif dataLenInt == 2:
        intStr = 'H'
    elif dataLenInt == 4:
        intStr = 'I'
    elif dataLenInt == 8:
        intStr = 'Q'
    else:
        intStr = ''

    fmtStr = f'<{intStr}{lenFloat}{floatStr}'

    return fmtStr


# former misspelled name, kept for compatibility
getFormatedStructString = getFormattedStructString


def packArrayToFrame(id: int, data: list[float], frameLen: int, dataLenFloat: int, dataLenInt: int) -> list[dict]:
    """
    Packs a data array into a list of payloads that do not exceed a given frame length

    :param id: Frame ID to use
    :type id: int
    :param data: Data to pack
    :type data: List of floats
    :param frameLen: Maximum size of frame for the given architecture
    :type frameLen: int
    :param dataLenFloat: Size of a float on the given architecture in bytes
    :type dataLenFloat: int
    :param dataLenInt: Size of an int on the given architecture in bytes
    :type dataLenInt: int

    :return: List of MIN-Frames, encoded in dictionaries with keys `id` and `msg`.
    """
    # the first frame carries the length of the array (occupying one float slot)
    # followed by floats, all following frames are filled with floats only
    restCnt = frameLen // dataLenFloat
    firstCnt = restCnt - 1
    if firstCnt < 0 or dataLenInt > dataLenFloat:
        raise ValueError("frameLen is too small for the given data types")

    values = [float(d) for d in data]
    first, rest = values[:firstCnt], values[firstCnt:]

    fmtStr = getFormattedStructString(dataLenFloat, dataLenInt, len(first))
    dataPoints = [{'id': id, 'msg': struct.pack(fmtStr, len(values), *first)}]
    for i in range(0, len(rest), restCnt):
        chunk = rest[i:i + restCnt]
        fmtStr = getFormattedStructString(dataLenFloat, 0, len(chunk))
        dataPoints.append({'id': id, 'msg': struct.pack(fmtStr, *chunk)})
    return dataPoints


# classes that used to live in this module, mapped to their new location
_MOVED = {
    'BufferView': 'pywisp.buffer',
    'DataPointBuffer': 'pywisp.buffer',
    'Exporter': 'pywisp.export',
    'DataIntDialog': 'pywisp.widgets.dialogs',
    'DataTcpIpDialog': 'pywisp.widgets.dialogs',
    'RemoteWidgetEdit': 'pywisp.widgets.dialogs',
    'ShortcutCreator': 'pywisp.widgets.dialogs',
    'FreeLayout': 'pywisp.widgets.remote',
    'MovableWidget': 'pywisp.widgets.remote',
    'MovablePushButton': 'pywisp.widgets.remote',
    'DoubleSlider': 'pywisp.widgets.remote',
    'MovableSlider': 'pywisp.widgets.remote',
    'MovableSwitch': 'pywisp.widgets.remote',
    'PlainTextLogger': 'pywisp.widgets.common',
    'PinnedDock': 'pywisp.widgets.common',
    'ContextLineEditAction': 'pywisp.widgets.common',
    'TreeWidgetStyledItemDelegate': 'pywisp.widgets.common',
}

# pickled measurements refer to these by their old path, so they stay available silently
_PICKLED = ('BufferView', 'DataPointBuffer')


def __getattr__(name):
    if name in _MOVED:
        module = _MOVED[name]
        if name not in _PICKLED:
            warnings.warn(f"pywisp.utils.{name} has moved, import it from {module} instead",
                          DeprecationWarning, stacklevel=2)
        return getattr(importlib.import_module(module), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
