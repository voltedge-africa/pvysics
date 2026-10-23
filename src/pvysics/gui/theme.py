"""The theme choice (System, Light or Dark), applied to the app and to the charts.

ThemeManager holds the choice, persists it with QSettings and emits `changed` with the palette in
effect whenever that may have changed. MainWindow applies the palette to the whole app through the
Fusion style and a QPalette, so the look is the same on Linux, macOS and Windows. Each chart is
restyled by style_plot from the views that own it, and each window's View menu (ThemeMenu) shows the
choice, so every window stays in step.
"""

import pyqtgraph as pg
from PyQt6.QtCore import QCoreApplication, QObject, QSettings, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import QApplication, QMainWindow

from pvysics.gui.palette import CHOICE_DARK, CHOICE_LIGHT, CHOICE_SYSTEM, CHOICES, Palette, palette_for

SETTINGS_KEY = "view/theme"
MENU_CHOICES = ((CHOICE_SYSTEM, "System"), (CHOICE_LIGHT, "Light"), (CHOICE_DARK, "Dark"))
# Error messages use Qt's BrightText role, so a label that uses it follows the palette without a stylesheet.
ERROR_ROLE = QPalette.ColorRole.BrightText


def default_settings() -> QSettings:
    """The app's settings store: an INI file in the user's configuration folder, the same on every platform."""
    return QSettings(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        QCoreApplication.organizationName(),
        QCoreApplication.applicationName(),
    )


class ThemeManager(QObject):
    """The theme choice and the palette it gives. `changed` carries the Palette now in effect."""

    changed = pyqtSignal(object)  # Palette

    def __init__(self, settings: QSettings | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = default_settings() if settings is None else settings
        stored = self._settings.value(SETTINGS_KEY, CHOICE_SYSTEM, type=str)
        self._choice = stored if stored in CHOICES else CHOICE_SYSTEM
        hints = QGuiApplication.styleHints()
        self._system_dark = hints.colorScheme() == Qt.ColorScheme.Dark
        hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    @property
    def choice(self) -> str:
        return self._choice

    @property
    def palette(self) -> Palette:
        return palette_for(self._choice, self._system_dark)

    def set_choice(self, choice: str) -> None:
        """Use and remember a choice. Every listener is told the palette in effect."""
        if choice not in CHOICES:
            raise ValueError(f"unknown theme choice {choice!r}")
        self._choice = choice
        self._settings.setValue(SETTINGS_KEY, choice)
        self.changed.emit(self.palette)

    def _on_system_scheme_changed(self, scheme: Qt.ColorScheme) -> None:
        """The operating system switched between light and dark. Only System follows it."""
        self._system_dark = scheme == Qt.ColorScheme.Dark
        if self._choice == CHOICE_SYSTEM:
            self.changed.emit(self.palette)


def apply_palette(palette: Palette) -> None:
    """Apply a palette to the whole application: the Fusion style and a QPalette built from it."""
    app = QApplication.instance()
    app.setStyle("Fusion")
    app.setPalette(qt_palette(palette))


def qt_palette(palette: Palette) -> QPalette:
    """The QPalette for a Palette. Roles not named here are derived from the window colour."""
    qt = QPalette(QColor(palette.window))
    roles = {
        QPalette.ColorRole.Window: palette.window,
        QPalette.ColorRole.WindowText: palette.text,
        QPalette.ColorRole.Base: palette.base,
        QPalette.ColorRole.AlternateBase: palette.window,
        QPalette.ColorRole.Text: palette.text,
        QPalette.ColorRole.Button: palette.card,
        QPalette.ColorRole.ButtonText: palette.text,
        QPalette.ColorRole.ToolTipBase: palette.base,
        QPalette.ColorRole.ToolTipText: palette.text,
        QPalette.ColorRole.PlaceholderText: palette.muted_text,
        QPalette.ColorRole.Highlight: palette.highlight,
        QPalette.ColorRole.HighlightedText: palette.highlight_text,
        QPalette.ColorRole.Link: palette.link,
        ERROR_ROLE: palette.error,
    }
    for role, colour in roles.items():
        qt.setColor(role, QColor(colour))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        qt.setColor(QPalette.ColorGroup.Disabled, role, QColor(palette.muted_text))
    return qt


def style_plot(plot: pg.PlotWidget, palette: Palette) -> None:
    """Background, axes, labels and legend of a chart in the palette. Series colours belong to the view."""
    plot.setBackground(palette.chart_background)
    for side in ("left", "bottom"):
        axis = plot.getAxis(side)
        axis.setPen(palette.chart_foreground)  # the axis line, its ticks and the grid lines
        axis.setTextPen(palette.chart_foreground)
    legend = plot.plotItem.legend
    if legend is not None:
        legend.setLabelTextColor(palette.chart_foreground)
        for _sample, label in legend.items:
            label.setText(label.text)  # a label takes a new colour only when its text is set again
        background = QColor(palette.chart_background)
        background.setAlpha(200)
        legend.setBrush(background)


class ThemeMenu(QObject):
    """The View menu's theme choices for one window. Every window's menu is driven by the same ThemeManager."""

    def __init__(self, window: QMainWindow, theme: ThemeManager) -> None:
        super().__init__(window)
        self._theme = theme
        self._actions: dict[str, QAction] = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        menu = window.menuBar().addMenu("&View")
        for choice, label in MENU_CHOICES:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(choice)
            group.addAction(action)
            menu.addAction(action)
            self._actions[choice] = action
        group.triggered.connect(self._on_chosen)
        theme.changed.connect(self._sync)
        self._sync(theme.palette)

    @property
    def actions(self) -> dict[str, QAction]:
        """The menu's actions keyed by choice: CHOICE_SYSTEM, CHOICE_LIGHT, CHOICE_DARK."""
        return dict(self._actions)

    def _on_chosen(self, action: QAction) -> None:
        self._theme.set_choice(action.data())

    def _sync(self, _palette: Palette) -> None:
        self._actions[self._theme.choice].setChecked(True)
