"""Figures drawn in QML: the Process screen's readings and the Dashboard's headline numbers.

The figures are plain type on the window, in groups divided by a hairline, with no boxes. One figure can be
the hero: the largest thing on screen, with the state under it and, for the deviation, a rail that shows where
it sits between the limits. The layout is MetricStrip.qml; this module is the Qt Widgets side of it. It keeps
the strip's data in one object that the QML reads, so a new value changes only the text it belongs to.

Quick uses software rendering (app.py sets it), so a strip needs no GPU and draws the same on every platform.
"""

from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QGuiApplication
from PyQt6.QtQuickWidgets import QQuickWidget
from PyQt6.QtWidgets import QWidget

from pvysics.gui.fonts import FIGURE_FAMILY, load_fonts
from pvysics.gui.palette import STATE_COLOURS, Palette
from pvysics.run import State

PLACEHOLDER = "-"
QML_FILE = Path(__file__).with_name("qml") / "MetricStrip.qml"
GAUGE_SCALE_FACTOR = 1.5  # the rail runs from minus to plus this multiple of the abnormal limit
SIZES = ("hero", "large", "medium", "small")


def split_reading(text: str) -> tuple[str, str]:
    """A reading such as "57 W/m²" as its number and its unit: ("57", "W/m²"). A bare "-" has no unit."""
    number, _space, unit = text.partition(" ")
    return number, unit


@dataclass(frozen=True)
class Tile:
    """One figure: its key, the caption over it, and its size (hero, large, medium or small)."""

    key: str
    caption: str
    size: str = "large"


@dataclass(frozen=True)
class Group:
    """Figures under a small title. columns is how many sit side by side (0 means all of them in one row);
    weight is the group's share of the strip's width (0 means one share per figure column)."""

    title: str
    tiles: list[Tile] = field(default_factory=list)
    columns: int = 0
    weight: int = 0
    spread: bool = False  # the figures share the group's width equally, instead of sitting at its left


class _StripData(QObject):
    """What the QML reads: the groups (structure), the values (text), the colours and the gauge."""

    structure_changed = pyqtSignal()
    values_changed = pyqtSignal()
    colours_changed = pyqtSignal()
    gauge_changed = pyqtSignal()

    def __init__(
        self, groups: list, font_family: str, unit_px: int, small_px: int, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._groups = groups
        self._values: dict[str, dict] = {}
        self._colours: dict[str, str] = {}
        self._gauge = {"active": False, "reading": 0.0, "warning": 5.0, "abnormal": 10.0, "scale": 15.0, "colour": ""}
        self._status = {"text": "", "colour": "transparent", "note": ""}
        self.font_family, self.unit_px, self.small_px = font_family, unit_px, small_px

    @pyqtProperty("QVariantList", notify=structure_changed)
    def groups(self) -> list:
        return self._groups

    @pyqtProperty("QVariantMap", notify=values_changed)
    def values(self) -> dict:
        return self._values

    @pyqtProperty("QVariantMap", notify=colours_changed)
    def colours(self) -> dict:
        return self._colours

    @pyqtProperty("QVariantMap", notify=gauge_changed)
    def gauge(self) -> dict:
        return self._gauge

    @pyqtProperty(str, constant=True)
    def fontFamily(self) -> str:
        return self.font_family

    @pyqtProperty(int, constant=True)
    def unitPx(self) -> int:
        return self.unit_px

    @pyqtProperty(int, constant=True)
    def smallPx(self) -> int:
        return self.small_px

    @pyqtProperty(str, constant=True)
    def figureFamily(self) -> str:
        return FIGURE_FAMILY

    status_changed = pyqtSignal()

    @pyqtProperty("QVariantMap", notify=status_changed)
    def status(self) -> dict:
        return self._status

    @pyqtProperty(str, constant=True)
    def normalColour(self) -> str:
        return STATE_COLOURS[State.NORMAL]

    @pyqtProperty(str, constant=True)
    def warningColour(self) -> str:
        return STATE_COLOURS[State.WARNING]

    @pyqtProperty(str, constant=True)
    def abnormalColour(self) -> str:
        return STATE_COLOURS[State.ABNORMAL]


class MetricStrip(QQuickWidget):
    """Figures in groups. groups is [(heading, [(key, caption), ...]), ...]; gauge_key names the figure that
    gets the deviation gauge beside it. Read a figure with value(key), write it with set_value."""

    def __init__(
        self,
        groups: list[Group],
        palette: Palette,
        gauge_key: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        load_fonts()
        self._texts: dict[str, str] = {}
        font = QGuiApplication.font()
        unit = max(QFontMetrics(font).height() // 2, 6)
        description = [_describe(group, gauge_key) for group in groups]
        self._data = _StripData(description, font.family(), unit, round(unit * 1.5), parent=self)
        for group in groups:
            for tile in group.tiles:
                self._texts[tile.key] = PLACEHOLDER
        self._fills: dict[str, tuple[str, str]] = {}
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.rootContext().setContextProperty("strip", self._data)
        self.set_palette(palette)
        self._push_values()
        self.setSource(QUrl.fromLocalFile(str(QML_FILE)))
        if self.status() != QQuickWidget.Status.Ready:
            errors = "; ".join(error.toString() for error in self.errors())
            raise RuntimeError(f"MetricStrip.qml did not load: {errors}")
        self.setFixedHeight(int(self.rootObject().implicitHeight()) + 1)

    def value(self, key: str) -> str:
        """The figure as shown, number and unit: "57 W/m²"."""
        return self._texts[key]

    def set_value(self, key: str, text: str, fill: str | None = None, text_colour: str | None = None) -> None:
        """Show text for a figure, optionally on a coloured pill (the State figure)."""
        self._texts[key] = text
        self._fills[key] = (fill or "", text_colour or "")
        self._push_values()

    def set_values(self, values: dict[str, str]) -> None:
        for key, text in values.items():
            if key not in self._texts:
                continue  # a figure this strip does not show
            self._texts[key] = text
            self._fills[key] = ("", "")
        self._push_values()

    def clear(self) -> None:
        for key in self._texts:
            self._texts[key] = PLACEHOLDER
        self._fills.clear()
        self._push_values()
        self.clear_gauge()
        self.set_status("")

    def fill(self, key: str) -> str | None:
        """The pill colour behind a figure, or None."""
        return self._fills.get(key, ("", ""))[0] or None

    def set_status(self, text: str, state: State | None = None, note: str = "") -> None:
        """The state word (and an optional note) under the hero figure, with a dot in the state's colour."""
        colour = "transparent" if state is None else STATE_COLOURS[state]
        self._data._status = {"text": text, "colour": colour, "note": note}
        self._data.status_changed.emit()

    @property
    def state_text(self) -> str:
        return self._data._status["text"]

    @property
    def state_note(self) -> str:
        return self._data._status["note"]

    @property
    def state_colour(self) -> str | None:
        colour = self._data._status["colour"]
        return None if colour == "transparent" else colour

    def set_gauge(self, deviation_pct: float, state: State, warning_pct: float, abnormal_pct: float) -> None:
        self._data._gauge = {
            "active": True,
            "reading": deviation_pct,
            "warning": warning_pct,
            "abnormal": abnormal_pct,
            "scale": GAUGE_SCALE_FACTOR * abnormal_pct,
            "colour": STATE_COLOURS[state],
        }
        self._data.gauge_changed.emit()

    def set_limits(self, warning_pct: float, abnormal_pct: float) -> None:
        """Move the gauge's limit marks and clear its reading."""
        self._data._gauge = {
            "active": False,
            "reading": 0.0,
            "warning": warning_pct,
            "abnormal": abnormal_pct,
            "scale": GAUGE_SCALE_FACTOR * abnormal_pct,
            "colour": "",
        }
        self._data.gauge_changed.emit()

    def clear_gauge(self) -> None:
        gauge = dict(self._data._gauge)
        gauge.update(active=False, reading=0.0)
        self._data._gauge = gauge
        self._data.gauge_changed.emit()

    @property
    def gauge_reading(self) -> float | None:
        """The deviation the gauge shows, in percent, or None when it shows none."""
        gauge = self._data._gauge
        return abs(gauge["reading"]) if gauge["active"] else None

    @property
    def colours(self) -> dict[str, str]:
        """The text, muted and rule colours the strip draws with."""
        return dict(self._data._colours)

    @property
    def gauge_state(self) -> State | None:
        """The State the gauge is coloured for, or None when it shows no reading."""
        colour = self._data._gauge["colour"]
        return next((state for state, value in STATE_COLOURS.items() if value == colour), None)

    @property
    def gauge_scale_pct(self) -> float:
        return self._data._gauge["scale"]

    def set_palette(self, palette: Palette) -> None:
        self._data._colours = {"text": palette.text, "muted": palette.muted_text, "rule": palette.card_border}
        self._data.colours_changed.emit()
        self.setClearColor(QColor(palette.window))

    def _push_values(self) -> None:
        shown = {}
        for key, text in self._texts.items():
            number, unit = split_reading(text)
            fill, fill_text = self._fills.get(key, ("", ""))
            shown[key] = {"number": number, "unit": unit, "fill": fill, "fillText": fill_text}
        self._data._values = shown
        self._data.values_changed.emit()


def _describe(group: Group, gauge_key: str) -> dict:
    """A group as the QML reads it."""
    columns = group.columns or len(group.tiles)
    has_gauge = any(tile.key == gauge_key for tile in group.tiles)
    return {
        "title": group.title,
        "columns": columns,
        "weight": group.weight or max(columns, 1),
        "gauge": has_gauge,
        "spread": group.spread,
        "tiles": [{"key": tile.key, "caption": tile.caption, "size": tile.size} for tile in group.tiles],
    }
