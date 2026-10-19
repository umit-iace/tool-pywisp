# -*- coding: utf-8 -*-
"""
Validation of the experiment configuration loaded from ``.sreg`` files.

Typos in the configuration would otherwise be silently ignored, so unknown or
malformed entries are reported. Deprecated keys are renamed to their current
name, malformed optional entries are dropped and experiments that cannot be
used at all are skipped.
"""
import copy
import logging

import yaml

__all__ = ["validateExperiments", "dumpExperiments"]

# top level keys of an experiment that do not denote an experiment module
RESERVED_KEYS = ('Name', 'Config', 'Remote', 'Visu')

DOWNSAMPLING_METHODS = ('peak', 'subsample', 'mean', 'off')


def _isNumber(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# allowed keys of the Config section and a check for their values
CONFIG_KEYS = {
    'TimerTime': (lambda v: _isNumber(v) and v > 0, "a positive number (ms)"),
    'HeartbeatTime': (lambda v: _isNumber(v) and v >= 0, "a non-negative number (ms)"),
    'MovingWindowEnable': (lambda v: isinstance(v, bool), "True or False"),
    'MovingWindowSize': (lambda v: _isNumber(v) and v > 0, "a positive number (s)"),
    'downsamplingMethod': (lambda v: v in DOWNSAMPLING_METHODS, f"one of {DOWNSAMPLING_METHODS}"),
}

# deprecated or misspelled keys of the Config section and their current name
CONFIG_ALIASES = {
    'Heartbeat': 'HeartbeatTime',
    'MovingWindowWidth': 'MovingWindowSize',
}

# required and optional keys (with defaults) of the remote widgets
# startValue is written by the widget editor, position is the place of the widget in the remote dock
REMOTE_COMMON_KEYS = ('widgetType', 'Module', 'Parameter', 'name', 'startValue', 'position')
REMOTE_KEYS = {
    'PushButton': {
        'required': ('valueOn',),
        'optional': {'valueReset': '', 'shortcut': '', 'shortcut-Gp': None},
    },
    'Switch': {
        'required': ('valueOn', 'valueOff'),
        'optional': {'shortcut': '', 'shortcut-Gp': None},
    },
    'Slider': {
        'required': ('minSlider', 'maxSlider', 'stepSlider'),
        'optional': {'shortcutPlus': '', 'shortcutMinus': '', 'shortcut-Gp': None, 'invertSlider': False},
    },
}


class _Report:
    """ collects the findings for one experiment """

    def __init__(self, logger, label):
        self.logger = logger
        self.label = label
        self.errors = 0

    def warning(self, msg):
        self.logger.warning(f"{self.label}: {msg}")

    def error(self, msg):
        self.errors += 1
        self.logger.error(f"{self.label}: {msg}")


def validateExperiments(experiments, modules, visualizers, logger=None):
    """
    Validates the experiments of a config file.

    :param experiments: list of experiments as loaded from the ``.sreg`` file, the entries are normalized in place
    :param modules: dict of registered experiment modules
    :param visualizers: dict of registered visualizers
    :param logger: logger to report the findings to
    :return: list of the usable experiments
    """
    logger = logger or logging.getLogger("Config")
    valid = []
    names = set()
    for idx, exp in enumerate(experiments):
        report = _Report(logger, f"Experiment {idx + 1}")
        if not isinstance(exp, dict):
            report.error("must be a mapping, skipping it")
            continue

        name = exp.get('Name')
        if name is None:
            report.error("has no 'Name', skipping it")
            continue
        exp['Name'] = name = str(name)
        report.label = f"Experiment '{name}'"
        if name in names:
            report.warning("the name is used more than once")
        names.add(name)

        moduleKeys = [key for key in exp if key not in RESERVED_KEYS]
        for key in moduleKeys:
            _checkModule(report, exp, key, modules)
        if report.errors:
            report.logger.error(f"{report.label}: skipping it due to the errors above")
            continue

        _checkConfig(report, exp)
        _checkVisu(report, exp, visualizers)
        _checkRemote(report, exp, modules)
        valid.append(exp)

    return valid


def _checkModule(report, exp, key, modules):
    if key not in modules:
        report.error(f"'{key}' is neither a registered experiment module nor one of {RESERVED_KEYS}")
        return
    settings = exp[key]
    if settings is None:
        return
    if not isinstance(settings, dict):
        report.error(f"the settings of module '{key}' must be a mapping")
        return
    known = modules[key].publicSettings
    for setting in settings:
        if setting not in known:
            report.warning(f"module '{key}' has no setting '{setting}', available are {list(known)}")


def _checkConfig(report, exp):
    config = exp.get('Config')
    if config is None:
        return
    if not isinstance(config, dict):
        report.warning("'Config' must be a mapping, ignoring it")
        del exp['Config']
        return

    for alias, key in CONFIG_ALIASES.items():
        if alias not in config:
            continue
        if key in config:
            report.warning(f"Config: '{alias}' is ignored, since '{key}' is given as well")
            del config[alias]
        else:
            report.warning(f"Config: '{alias}' is deprecated, use '{key}' instead")
            config[key] = config.pop(alias)

    for key in list(config):
        if key not in CONFIG_KEYS:
            report.warning(f"Config: unknown key '{key}', available are {list(CONFIG_KEYS)}")
            continue
        check, expected = CONFIG_KEYS[key]
        if not check(config[key]):
            report.warning(f"Config: '{key}' must be {expected}, got {config[key]!r}. Using the default instead")
            del config[key]


def _checkVisu(report, exp, visualizers):
    visu = exp.get('Visu')
    if visu is None:
        return
    if isinstance(visu, str):
        visu = [visu]
    if not isinstance(visu, (dict, list)):
        report.warning("'Visu' must be a list or mapping of visualizer names, ignoring it")
        del exp['Visu']
        return
    for name in visu:
        if name not in visualizers:
            report.warning(f"Visu: '{name}' is not a registered visualizer")


def _checkRemote(report, exp, modules):
    remote = exp.get('Remote')
    if remote is None:
        return
    if not isinstance(remote, dict):
        report.warning("'Remote' must be a mapping of widgets, ignoring it")
        del exp['Remote']
        return

    for widgetName in list(remote):
        problem = _checkWidget(report, widgetName, remote[widgetName], exp, modules)
        if problem:
            report.warning(f"Remote: ignoring widget '{widgetName}', {problem}")
            del remote[widgetName]


def _checkWidget(report, widgetName, widget, exp, modules):
    """
    Checks and normalizes the config of a remote widget.
    :return: description of the problem if the widget cannot be used, otherwise `None`
    """
    if not isinstance(widget, dict):
        return "its config must be a mapping"

    widgetType = widget.get('widgetType')
    if widgetType not in REMOTE_KEYS:
        return f"'widgetType' must be one of {list(REMOTE_KEYS)}, got {widgetType!r}"
    spec = REMOTE_KEYS[widgetType]

    module, parameter = widget.get('Module'), widget.get('Parameter')
    if module not in exp or module in RESERVED_KEYS:
        return f"'Module' must name a module of this experiment, got {module!r}"
    if parameter not in modules[module].publicSettings:
        return f"module '{module}' has no setting {parameter!r}"

    missing = [key for key in spec['required'] if key not in widget]
    if missing:
        return f"missing the key(s) {missing}"

    allowed = set(REMOTE_COMMON_KEYS) | set(spec['required']) | set(spec['optional'])
    unknown = [key for key in widget if key not in allowed]
    if unknown:
        report.warning(f"Remote: widget '{widgetName}' has unknown key(s) {unknown}")

    position = widget.get('position')
    if position is not None and not (isinstance(position, (list, tuple)) and len(position) == 2
                                     and all(_isNumber(v) and v >= 0 for v in position)):
        report.warning(f"Remote: widget '{widgetName}' has an invalid position {position!r}, "
                       f"expected [x, y] with non-negative numbers")
        del widget['position']

    for key, default in spec['optional'].items():
        if widget.get(key) is None:
            widget[key] = default
    return None


def dumpExperiments(experiments):
    """
    Converts experiments to the yaml format of the ``.sreg`` files.

    The name stored in the widget configs and optional widget entries holding their
    default value are omitted.

    :param experiments: list of experiments
    :return: yaml text
    """
    experiments = copy.deepcopy(experiments)
    for exp in experiments:
        remote = exp.get('Remote') if isinstance(exp, dict) else None
        if not isinstance(remote, dict):
            continue
        for widget in remote.values():
            if not isinstance(widget, dict):
                continue
            widget.pop('name', None)
            spec = REMOTE_KEYS.get(widget.get('widgetType'), {'optional': {}})
            for key, default in spec['optional'].items():
                if key in widget and widget[key] in (None, default):
                    del widget[key]
            if 'position' in widget:
                widget['position'] = [int(v) for v in widget['position']]
    return yaml.safe_dump(experiments, sort_keys=False, default_flow_style=None, allow_unicode=True)
