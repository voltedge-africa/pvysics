"""Small helpers for widgets that take their look from the stylesheet (gui/style.py)."""

import pyqtgraph as pg
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QLabel, QWidget

PLOT_HINT = QSize(320, 220)


def set_property(widget: QWidget, name: str, value: str) -> None:
    """Set a style property such as role or variant and make the stylesheet apply the change now."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def role_label(text: str, role: str, alignment=None) -> QLabel:
    """A label whose size and colour come from the stylesheet's role (caption, muted, value, hero, title)."""
    label = QLabel(text)
    label.setProperty("role", role)
    if alignment is not None:
        label.setAlignment(alignment)
    return label


class CompactPlot(pg.PlotWidget):
    """A chart that asks for a modest size. pyqtgraph's own hint is 640 by 480, which makes a grid of charts
    very tall and a scroll area scroll far. The chart still grows to fill the space it is given."""

    hint = PLOT_HINT  # an instance can ask for less, for a chart that shares a screen with other things

    def sizeHint(self) -> QSize:
        return self.hint
