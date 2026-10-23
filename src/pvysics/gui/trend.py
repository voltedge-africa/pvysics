"""A live trend of measured and predicted power, for the Process view.

It shows the run so far so the operator sees how the plant tracks the twin and when a fault began.
Samples are buffered and drawn once per UI tick, so a fast run costs one setData per curve per tick.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QSize, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from pvysics.gui.palette import Palette
from pvysics.gui.ui_helpers import CompactPlot
from pvysics.gui.theme import style_plot
from pvysics.run import Sample

UI_TICK_MS = 100
MIN_PLOT_HEIGHT_PX = 110
PLOT_HINT = QSize(320, 150)  # the trend shares the Process screen with cards, faults and alarms


class PowerTrend(QWidget):
    """Measured and predicted power against time since the run began, with a marker where faults change."""

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette
        self._origin: np.datetime64 | None = None
        self._hours: list[float] = []
        self._measured: list[float] = []
        self._predicted: list[float] = []
        self._faults: tuple = ()
        self._markers: list[pg.InfiniteLine] = []
        self._dirty = False

        self.plot = CompactPlot()
        self.plot.hint = PLOT_HINT
        self.plot.setMinimumHeight(MIN_PLOT_HEIGHT_PX)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMenuEnabled(False)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("left", "Power (W)")
        self.plot.setLabel("bottom", "Time since start (h)")
        self.plot.enableAutoRange(x=True, y=True)
        self.plot.addLegend(offset=(10, 10))
        self.measured_curve = self.plot.plot([], [], name="P measured")
        self.predicted_curve = self.plot.plot([], [], name="P predicted")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)
        self.apply_palette(palette)

        self._timer = QTimer(self)
        self._timer.setInterval(UI_TICK_MS)
        self._timer.timeout.connect(self.flush)
        self._timer.start()

    @property
    def point_count(self) -> int:
        """How many samples the trend holds."""
        return len(self._hours)

    @property
    def marker_count(self) -> int:
        """How many fault markers are drawn."""
        return len(self._markers)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        style_plot(self.plot, palette)
        self.measured_curve.setPen(pg.mkPen(palette.measured, width=2))
        self.predicted_curve.setPen(pg.mkPen(palette.predicted, width=2, style=pg.QtCore.Qt.PenStyle.DashLine))
        for marker in self._markers:
            marker.setPen(pg.mkPen(palette.muted_text, width=1, style=pg.QtCore.Qt.PenStyle.DashLine))
        self.plot.setBackground(QColor(palette.chart_background))

    def add_sample(self, sample: Sample) -> None:
        """Buffer a Sample. It is drawn at the next UI tick (or at flush)."""
        if self._origin is None:
            self._origin = sample.timestamp
        hours = float((sample.timestamp - self._origin) / np.timedelta64(1, "h"))
        self._hours.append(hours)
        self._measured.append(sample.power_measured)
        self._predicted.append(sample.power_predicted)
        if sample.active_faults != self._faults:
            self._faults = sample.active_faults
            self._add_marker(hours)
        self._dirty = True

    def clear(self) -> None:
        self._origin = None
        self._hours.clear()
        self._measured.clear()
        self._predicted.clear()
        self._faults = ()
        for marker in self._markers:
            self.plot.removeItem(marker)
        self._markers.clear()
        self.measured_curve.setData([], [])
        self.predicted_curve.setData([], [])
        self._dirty = False

    def flush(self) -> None:
        """Draw what has been buffered since the last flush, with one setData per curve."""
        if not self._dirty:
            return
        self.measured_curve.setData(self._hours, self._measured)
        self.predicted_curve.setData(self._hours, self._predicted)
        self._dirty = False

    def _add_marker(self, hours: float) -> None:
        pen = pg.mkPen(self._palette.muted_text, width=1, style=pg.QtCore.Qt.PenStyle.DashLine)
        marker = pg.InfiniteLine(pos=hours, angle=90, pen=pen)
        self.plot.addItem(marker)
        self._markers.append(marker)
