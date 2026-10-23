"""The Dashboard's Live charts tab: voltage and current, the I-V and P-V curves with the measured operating
point, cumulative energy, the power deviation histogram, and the time in each State.

Every chart is restyled from the palette, and created in the palette in effect. Each UI tick the
Dashboard passes the Samples that arrived since the last tick: the curves are handed their full
columns once per tick (one setData each), and the histogram and the state times take only the new
Samples (live_stats). The I-V and P-V curves are for the measured G and T, as on the Model tab, and
are recomputed only when G or T has moved. At night the curve collapses to nothing, so the last
daylight curve stays on show and the operating point moves on it.
"""

from typing import TYPE_CHECKING

import pyqtgraph as pg
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pvysics.datasheet import ModuleDatasheet
from pvysics.gui.palette import STATE_COLOURS, Palette
from pvysics.gui.theme import style_plot
from pvysics.live_stats import HISTOGRAM_LIMIT_PCT, DeviationHistogram, StateTimes
from pvysics.run import POWER_FLOOR_W, Sample, State
from pvysics.single_diode import IVCurve, fit_parameters, solve_curve

if TYPE_CHECKING:
    from pvysics.gui.dashboard import SampleColumns

STATE_ORDER = (State.NORMAL, State.WARNING, State.ABNORMAL)
TIME_LABEL = "Time since start (h)"
PLOT_LINES = 8  # a plot is never shorter than this many text lines, so its axes stay legible


def _plain_plot(minimum_height: int) -> pg.PlotWidget:
    """A chart whose axes show plain values. Auto SI prefixes would turn 0.2 A into 200 (x0.001), so they are off."""
    plot = pg.PlotWidget()
    for side in ("left", "bottom"):
        plot.getAxis(side).enableAutoSIPrefix(False)
    plot.setMinimumHeight(minimum_height)
    return plot


def _time_plot(left_label: str, minimum_height: int) -> pg.PlotWidget:
    plot = _plain_plot(minimum_height)
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.setLabel("left", left_label)
    plot.setLabel("bottom", TIME_LABEL)
    return plot


def _curve_plot(left_label: str, minimum_height: int) -> pg.PlotWidget:
    plot = _plain_plot(minimum_height)
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.setLabel("left", left_label)
    plot.setLabel("bottom", "Voltage (V)")
    return plot


def _point_item(plot: pg.PlotWidget) -> pg.ScatterPlotItem:
    """The measured operating point, drawn on top of a curve."""
    point = pg.ScatterPlotItem(size=12, pen=pg.mkPen(None))
    point.setZValue(10)
    plot.addItem(point)
    return point


class LiveCharts(QWidget):
    """Five live views of the run, in a grid: voltage and current, I-V and P-V, energy, histogram, state time."""

    def __init__(self, datasheet: ModuleDatasheet, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._datasheet = datasheet
        self._parameters = fit_parameters(datasheet)  # the same fit the Model tab and the twin use
        self._curve: IVCurve | None = None
        self._curve_key: tuple[float, float] | None = None
        self._histogram = DeviationHistogram()
        self._states = StateTimes()
        minimum = self.fontMetrics().height() * PLOT_LINES
        self._build_charts(minimum)
        self._build_layout()
        self._show_histogram()
        self._show_state_times()
        self.apply_palette(palette)

    @property
    def curve(self) -> IVCurve | None:
        """The I-V and P-V curves on show, or None before a Sample has arrived."""
        return self._curve

    @property
    def curve_key(self) -> tuple[float, float] | None:
        """The measured (G, T) the curves were computed for."""
        return self._curve_key

    @property
    def histogram(self) -> DeviationHistogram:
        return self._histogram

    @property
    def state_times(self) -> StateTimes:
        return self._states

    def apply_palette(self, palette: Palette) -> None:
        """Restyle the charts and their curves, bars and points for a palette."""
        for plot in (
            self.voltage_plot,
            self.current_plot,
            self.iv_plot,
            self.pv_plot,
            self.energy_plot,
            self.histogram_plot,
            self.state_plot,
        ):
            style_plot(plot, palette)
        self._voltage.setPen(pg.mkPen(palette.voltage, width=2))
        self._current.setPen(pg.mkPen(palette.current, width=2))
        self._energy.setPen(pg.mkPen(palette.measured, width=2))
        self._iv_curve.setPen(pg.mkPen(palette.model_iv, width=2))
        self._pv_curve.setPen(pg.mkPen(palette.model_pv, width=2))
        for point in (self._iv_point, self._pv_point):
            point.setBrush(pg.mkBrush(palette.operating_point))
        self._histogram_bars.setOpts(brush=pg.mkBrush(QColor(palette.deviation)))

    def set_datasheet(self, datasheet: ModuleDatasheet) -> None:
        """Follow the applied config's module. The curves are recomputed for the next Sample."""
        self._datasheet = datasheet
        self._parameters = fit_parameters(datasheet)
        self._curve_key = None

    def update(self, columns: "SampleColumns", new_samples: list[Sample]) -> None:
        """The UI tick: plot the run so far, given the Samples that arrived since the last tick."""
        if not new_samples:
            return
        self._histogram.add(new_samples)
        self._states.add(new_samples)
        self._show_operating_curves(new_samples)
        hours = columns.column("hours")
        self._voltage.setData(hours, columns.column("voltage"))
        self._current.setData(hours, columns.column("current"))
        self._energy.setData(hours, columns.column("energy_wh"))
        self._show_histogram()
        self._show_state_times()

    def clear(self) -> None:
        """Empty every chart: a reset starts the run again."""
        self._histogram.clear()
        self._states.clear()
        self._curve = None
        self._curve_key = None
        for item in (self._voltage, self._current, self._energy, self._iv_curve, self._pv_curve):
            item.setData([], [])
        for point in (self._iv_point, self._pv_point):
            point.setData([], [])
        self._show_histogram()
        self._show_state_times()

    def _show_operating_curves(self, new_samples: list[Sample]) -> None:
        daylight = next((s for s in reversed(new_samples) if s.power_predicted >= POWER_FLOOR_W), None)
        if daylight is not None:
            key = (daylight.measured_irradiance, daylight.measured_temperature)
            if key != self._curve_key:
                self._curve = solve_curve(self._datasheet, key[0], key[1], self._parameters)
                self._curve_key = key
                self._iv_curve.setData(self._curve.voltage, self._curve.current)
                self._pv_curve.setData(self._curve.voltage, self._curve.power)
        sample = new_samples[-1]
        self._iv_point.setData([sample.measured_voltage], [sample.measured_current])
        self._pv_point.setData([sample.measured_voltage], [sample.power_measured])

    def _show_histogram(self) -> None:
        histogram = self._histogram
        self._histogram_bars.setOpts(
            x=histogram.centres, height=histogram.counts, width=histogram.bin_width_pct
        )
        self.histogram_caption.setText(
            f"{histogram.total} daylight samples in {-HISTOGRAM_LIMIT_PCT:g} to +{HISTOGRAM_LIMIT_PCT:g} % "
            f"({histogram.below_range} below, {histogram.above_range} above)"
        )

    def _show_state_times(self) -> None:
        minutes = [self._states.seconds_in(state) / 60.0 for state in STATE_ORDER]
        self._state_bars.setOpts(height=minutes)
        self.state_caption.setText(
            "   ".join(
                f"{state.value} {self._states.seconds_in(state) / 60.0:.1f} min "
                f"({self._states.fraction_in(state):.0%})"
                for state in STATE_ORDER
            )
        )

    def _build_charts(self, minimum: int) -> None:
        self.voltage_plot = _time_plot("Voltage (V)", minimum)
        self.voltage_plot.hideAxis("bottom")  # the current plot below shares the time axis
        self._voltage = self.voltage_plot.plot()
        self.current_plot = _time_plot("Current (A)", minimum)
        self.current_plot.setXLink(self.voltage_plot)
        self._current = self.current_plot.plot()

        self.iv_plot = _curve_plot("Current (A)", minimum)
        self.pv_plot = _curve_plot("Power (W)", minimum)
        self._iv_curve = self.iv_plot.plot()
        self._pv_curve = self.pv_plot.plot()
        self._iv_point = _point_item(self.iv_plot)
        self._pv_point = _point_item(self.pv_plot)

        self.energy_plot = _time_plot("Energy (Wh)", minimum)
        self._energy = self.energy_plot.plot()

        self.histogram_plot = _plain_plot(minimum)
        self.histogram_plot.showGrid(y=True, alpha=0.3)
        self.histogram_plot.setLabel("left", "Samples")
        self.histogram_plot.setLabel("bottom", "Power deviation (%)")
        self._histogram_bars = pg.BarGraphItem(
            x=self._histogram.centres,
            height=self._histogram.counts,
            width=self._histogram.bin_width_pct,
            pen=pg.mkPen(None),
        )
        self.histogram_plot.addItem(self._histogram_bars)
        self.histogram_caption = _caption()

        self.state_plot = _plain_plot(minimum)
        self.state_plot.showGrid(y=True, alpha=0.3)
        self.state_plot.setLabel("left", "Time (min)")
        self.state_plot.setXRange(-0.5, len(STATE_ORDER) - 0.5, padding=0)
        self.state_plot.getAxis("bottom").setTicks([[(index, state.value) for index, state in enumerate(STATE_ORDER)]])
        self._state_bars = pg.BarGraphItem(
            x=list(range(len(STATE_ORDER))),
            height=[0.0] * len(STATE_ORDER),
            width=0.6,
            brushes=[pg.mkBrush(STATE_COLOURS[state]) for state in STATE_ORDER],
            pen=pg.mkPen(None),
        )
        self.state_plot.addItem(self._state_bars)
        self.state_caption = _caption()

    def _build_layout(self) -> None:
        voltage_current = QGroupBox("Voltage and current")
        voltage_layout = QVBoxLayout(voltage_current)
        voltage_layout.addWidget(self.voltage_plot, 1)
        voltage_layout.addWidget(self.current_plot, 1)

        curves = QGroupBox("I-V and P-V curve at the measured G and T, with the operating point")
        curve_row = QHBoxLayout(curves)
        curve_row.addWidget(self.iv_plot, 1)
        curve_row.addWidget(self.pv_plot, 1)

        energy = _framed("Cumulative energy", self.energy_plot)
        histogram = _framed("Power deviation (daylight)", self.histogram_plot, self.histogram_caption)
        states = _framed("Time in each state", self.state_plot, self.state_caption)

        grid = QGridLayout(self)
        grid.addWidget(voltage_current, 0, 0)
        grid.addWidget(curves, 0, 1, 1, 2)
        grid.addWidget(energy, 1, 0)
        grid.addWidget(histogram, 1, 1)
        grid.addWidget(states, 1, 2)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        for row in range(2):
            grid.setRowStretch(row, 1)


def _caption() -> QLabel:
    label = QLabel()
    label.setWordWrap(True)  # a long caption wraps rather than widening its chart
    return label


def _framed(title: str, plot: pg.PlotWidget, caption: QLabel | None = None) -> QGroupBox:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.addWidget(plot, 1)
    if caption is not None:
        layout.addWidget(caption)
    return box
