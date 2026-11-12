# -*- coding: utf-8 -*-
"""
Color themes of the gui: the native look of the system and light and dark palettes,
the dark one follows pymoskito.
"""
from PyQt6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import QApplication

__all__ = ["THEMES", "applyTheme", "isDark", "themedIcon"]


def _palette(window, base, text, highlight, disabled):
    # derives the shades used for bevels from the window color
    palette = QPalette(QColor(window))
    roles = {
        QPalette.ColorRole.Window: window,
        QPalette.ColorRole.WindowText: text,
        QPalette.ColorRole.Base: base,
        QPalette.ColorRole.AlternateBase: window,
        QPalette.ColorRole.ToolTipBase: window,
        QPalette.ColorRole.ToolTipText: text,
        QPalette.ColorRole.PlaceholderText: disabled,
        QPalette.ColorRole.Text: text,
        QPalette.ColorRole.Button: window,
        QPalette.ColorRole.ButtonText: text,
        QPalette.ColorRole.Highlight: highlight,
        QPalette.ColorRole.HighlightedText: '#ffffff',
        QPalette.ColorRole.Link: highlight,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(disabled))
    return palette


#: name: (dark theme, palette), `None` keeps the style and palette of the system
THEMES = {
    'System': (False, None),
    'Light': (False, lambda: _palette('#efefef', '#ffffff', '#101010', '#308cc6', '#7f7f7f')),
    'Dark': (True, lambda: _palette('#353535', '#191919', '#efefef', '#1e90ff', '#7f7f7f')),
    'Solarized Light': (False, lambda: _palette('#eee8d5', '#fdf6e3', '#586e75', '#268bd2', '#93a1a1')),
    'Solarized Dark': (True, lambda: _palette('#073642', '#002b36', '#93a1a1', '#268bd2', '#586e75')),
}

# style name and palette of the system, taken before the first theme is applied
_system = None


def applyTheme(name):
    """ applies the theme with the given name to the whole application """
    global _system
    app = QApplication.instance()
    palette = THEMES[name][1]
    if _system is None:
        _system = (app.style().name(), app.palette())
        if palette is None:
            return
    style, palette = _system if palette is None else ('Fusion', palette())
    # the palette first: setting the style polishes all widgets again with it, widgets below a
    # style sheet (e.g. the content of the docks) would keep the old palette otherwise
    app.setPalette(palette)
    # native styles, e.g. the one of windows, ignore the palette
    app.setStyle(style)


def isDark(name):
    return THEMES[name][0]


def themedIcon(resPath, color=None):
    """ the monochrome icon in the given color, default the text color of the current theme """
    pixmap = QPixmap(resPath)
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color) if color else QApplication.palette().color(QPalette.ColorRole.WindowText))
    painter.end()
    return QIcon(pixmap)
