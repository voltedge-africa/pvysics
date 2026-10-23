"""The tiles of the Process screen's measurement row: a caption, a large number and a small unit.

Each metric is a tile of its own, so the eye can pick one out. The number is the point; the unit is
beside it and smaller.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pvysics.gui.ui_helpers import role_label

PLACEHOLDER = "-"


def split_reading(text: str) -> tuple[str, str]:
    """A reading such as "57 W/m²" as its number and its unit: ("57", "W/m²"). A bare "-" has no unit."""
    number, _space, unit = text.partition(" ")
    return number, unit


class MetricTile(QFrame):
    """One metric: caption on top, the number large, the unit small beside it."""

    def __init__(self, caption: str, parent: QWidget | None = None, side: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricTile")
        self.setProperty("card", "true")
        self._number = role_label(PLACEHOLDER, "metric")
        self._unit = role_label("", "unit")
        figure = QHBoxLayout()
        figure.setSpacing(4)
        figure.addWidget(self._number)
        figure.addWidget(self._unit, 0, Qt.AlignmentFlag.AlignBottom)
        figure.addStretch(1)
        words = QVBoxLayout()
        words.setSpacing(0)
        words.addWidget(role_label(caption, "caption"))
        words.addLayout(figure)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addLayout(words)
        if side is not None:  # a widget beside the figure, such as the deviation gauge
            layout.addWidget(side, 1)

    def text(self) -> str:
        """The reading as shown, number and unit: "57 W/m²"."""
        unit = self._unit.text()
        return f"{self._number.text()} {unit}" if unit else self._number.text()

    def set_text(self, text: str) -> None:
        number, unit = split_reading(text)
        self._number.setText(number)
        self._unit.setText(unit)

    def clear(self) -> None:
        self.set_text(PLACEHOLDER)


class MetricSet:
    """A group of tiles read and written by key. The Process view's plant and twin are each one."""

    def __init__(self, tiles: dict[str, MetricTile]) -> None:
        self.tiles = tiles

    def value(self, key: str) -> str:
        return self.tiles[key].text()

    def set_values(self, values: dict[str, str]) -> None:
        for key, tile in self.tiles.items():
            tile.set_text(values[key])

    def clear(self) -> None:
        for tile in self.tiles.values():
            tile.clear()


def section_label(text: str) -> QLabel:
    """A small heading over a group of tiles, with a rule under it."""
    return role_label(text.upper(), "section")
