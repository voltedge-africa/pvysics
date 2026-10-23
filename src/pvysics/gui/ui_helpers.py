"""Small helpers for widgets that take their look from the stylesheet (gui/style.py)."""

import pyqtgraph as pg
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QFrame, QLabel, QWidget

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


class ElidedLabel(QLabel):
    """A one-line label that shortens its text with an ellipsis instead of widening its row.

    text() is the whole text. The toolbar's status sentence uses it, so a long sentence never pushes the
    buttons off the row; the full text is the tooltip.
    """

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        shown = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        painter.setPen(self.palette().windowText().color())
        painter.drawText(self.rect(), int(self.alignment()), shown)
        painter.end()


def vertical_separator() -> QFrame:
    """A thin vertical rule between groups of toolbar controls."""
    rule = QFrame()
    rule.setObjectName("toolSeparator")
    rule.setFixedWidth(1)
    return rule
