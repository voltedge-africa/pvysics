"""Small helpers for widgets that take their look from the stylesheet (gui/style.py)."""

from pathlib import Path

import pyqtgraph as pg
from pyqtgraph.exporters import CSVExporter, ImageExporter
from PyQt6.QtCore import QEvent, QRectF, QSize, Qt
from PyQt6.QtGui import QAction, QColor, QPainter, QPen
from PyQt6.QtWidgets import QDockWidget, QFileDialog, QFrame, QHBoxLayout, QLabel, QMenu, QToolButton, QWidget

PLOT_HINT = QSize(320, 220)
EXPORT_MARGIN_PX = 6
PANE_PADDING_PX = 10  # space between a pane's border and its content


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


def pane(widget: QWidget) -> QFrame:
    """Wrap content in a hairline border with padding, so neighbouring panes read as separate."""
    frame = QFrame()
    frame.setProperty("pane", "true")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(PANE_PADDING_PX, PANE_PADDING_PX, PANE_PADDING_PX, PANE_PADDING_PX)
    layout.addWidget(widget)
    return frame


class FloatingDock(QDockWidget):
    """A dock that, while it floats as a window of its own, has a solid background (white in the light theme: the
    palette's base colour) and a green border. Docked, it is transparent and borderless."""

    BORDER_PX = 2

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.topLevelChanged.connect(self._on_floating_changed)

    def paintEvent(self, event) -> None:
        if self.isFloating():
            painter = QPainter(self)
            painter.fillRect(self.rect(), self.palette().base())  # solid: the theme's base colour
            painter.end()
        super().paintEvent(event)
        if self.isFloating():
            painter = QPainter(self)
            half = self.BORDER_PX / 2
            painter.setPen(QPen(self.palette().highlight().color(), self.BORDER_PX))
            painter.drawRect(QRectF(self.rect()).adjusted(half, half, -half, -half))
            painter.end()

    def _on_floating_changed(self, floating: bool) -> None:
        self._restyle()

    def _restyle(self) -> None:
        # The dock paints its own border while floating, so its pane drops the hairline (a stylesheet rule
        # keyed on the dock's :floating state does not reach the pane, and leaves every docked pane unbordered)
        pane_state = "floating" if self.isFloating() else "true"
        for frame in self.findChildren(QFrame):
            if frame.property("pane") is not None:
                set_property(frame, "pane", pane_state)
        self.update()


class ChartDock(FloatingDock):
    """A dock for a chart or two. While it floats its charts take the same solid colour as the dock."""

    def __init__(self, title: str, widget: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setObjectName(f"dock_{title}")
        self.setWidget(pane(widget))
        self._chart_background = "#ffffff"

    def set_chart_background(self, chart_background: str) -> None:
        """The colour the charts have while docked; call it whenever the theme changes."""
        self._chart_background = chart_background
        self._restyle()

    def _restyle(self) -> None:
        super()._restyle()
        colour = self.palette().base().color() if self.isFloating() else QColor(self._chart_background)
        for plot in self.findChildren(pg.PlotWidget):
            plot.setBackground(colour)


def unit_row(field: QWidget, unit: str) -> QWidget:
    """A field with its unit in a muted label beside it, so the number field holds only the number."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(field)
    layout.addWidget(role_label(unit, "muted"))
    layout.addStretch(1)
    return row


class CompactPlot(pg.PlotWidget):
    """A chart that asks for a modest size, and that can be explored and exported.

    pyqtgraph's own hint is 640 by 480, which makes a grid of charts very tall; this one asks for less and
    still grows to fill the space it is given. The mouse wheel zooms and a drag pans. While the pointer is
    over the chart an Export button shows at its top right corner, with the image and the data of the
    chart (as currently zoomed, for the image) and a way back to the full view.
    """

    hint = PLOT_HINT  # an instance can ask for less, for a chart that shares a screen with other things

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self.export_button = QToolButton(self)
        self.export_button.setText("Export")
        self.export_button.setProperty("role", "chartExport")
        self.export_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.export_button.setCursor(Qt.CursorShape.ArrowCursor)
        menu = QMenu(self.export_button)
        self.image_action = QAction("Image (PNG)...", menu)
        self.image_action.triggered.connect(self._on_image_chosen)
        self.data_action = QAction("Data (CSV)...", menu)
        self.data_action.triggered.connect(self._on_data_chosen)
        self.reset_action = QAction("Reset view", menu)
        self.reset_action.triggered.connect(self.reset_view)
        menu.addActions([self.image_action, self.data_action])
        menu.addSeparator()
        menu.addAction(self.reset_action)
        self.export_button.setMenu(menu)
        self.export_button.hide()
        self.export_button.adjustSize()

    def sizeHint(self) -> QSize:
        return self.hint

    def reset_view(self) -> None:
        """Back to the whole chart."""
        self.enableAutoRange()

    def export_image(self, path: str) -> None:
        """Save the chart as it is on screen, as a PNG."""
        ImageExporter(self.plotItem).export(path)

    def export_data(self, path: str) -> None:
        """Save every curve of the chart as CSV, x first."""
        CSVExporter(self.plotItem).export(path)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._place_export_button()
        self.export_button.show()
        self.export_button.raise_()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if not self.export_button.menu().isVisible():
            self.export_button.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_export_button()

    def _place_export_button(self) -> None:
        button = self.__dict__.get("export_button")  # pyqtgraph resizes the chart before our button exists
        if button is None:
            return
        button.adjustSize()
        button.move(self.width() - button.width() - EXPORT_MARGIN_PX, EXPORT_MARGIN_PX)

    def _on_image_chosen(self, *_args) -> None:
        self._save("Export image", "PNG image (*.png)", ".png", self.export_image)

    def _on_data_chosen(self, *_args) -> None:
        self._save("Export data", "CSV file (*.csv)", ".csv", self.export_data)

    def _save(self, title: str, name_filter: str, suffix: str, write) -> None:
        path, _chosen = QFileDialog.getSaveFileName(self, title, "", name_filter)
        if path:
            write(str(Path(path).with_suffix(suffix)))


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
