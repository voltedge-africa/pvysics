"""The Dashboard window: read-only analytics on the same run as the HMI.

Layout follows the dashboard wireframe: KPI tiles on top, measured vs predicted power and
the deviation chart in the middle, irradiance and temperature with the event log below.
The Dashboard has no controls that change the run; it subscribes to the DataBus for new data
and reads the run's history on each UI tick. Plots are updated once per tick, with only the
Samples that arrived since the last tick appended, so a full day stays responsive.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from pvysics.gui.data_bus import DataBus
from pvysics.gui.process_view import (
    GAUGE_SCALE_FACTOR,
    PLACEHOLDER,
    STATE_COLOURS,
    STATE_TEXT_COLOURS,
    format_readings,
)
from pvysics.history import RunHistory
from pvysics.run import Event, Sample, State, Thresholds

UI_INTERVAL_MS = 100  # the Dashboard refreshes at most this often
BAND_ALPHA = 0.35
TIME_LABEL = "Time since start (h)"
COLUMNS = ("hours", "power_measured", "power_predicted", "deviation", "irradiance", "temperature")
COLUMN_INDEX = {name: index for index, name in enumerate(COLUMNS)}
INITIAL_CAPACITY = 1024
MEASURED_COLOUR = "#1565c0"
PREDICTED_COLOUR = "#ef6c00"
DEVIATION_COLOUR = "#424242"
IRRADIANCE_COLOUR = "#f9a825"
TEMPERATURE_COLOUR = "#c62828"


def format_event(event: Event) -> str:
    stamp = np.datetime_as_string(event.timestamp, unit="m").split("T")[1]
    label = "State" if event.kind == "state" else "Fault"
    return f"{stamp}  {label}: {event.detail}"


class SampleColumns:
    """The plotted values of the run so far, one column per name in COLUMNS.

    Rows are appended in place into arrays that grow by doubling, so an append costs only
    the new Samples and a read is a view.
    """

    def __init__(self) -> None:
        self._data = np.empty((len(COLUMNS), INITIAL_CAPACITY))
        self._count = 0

    def clear(self) -> None:
        self._count = 0

    def append(self, samples: list[Sample], origin: np.datetime64) -> None:
        rows = np.array([_row(sample, origin) for sample in samples], dtype=float).T
        needed = self._count + rows.shape[1]
        if needed > self._data.shape[1]:
            grown = np.empty((len(COLUMNS), max(needed, 2 * self._data.shape[1])))
            grown[:, : self._count] = self._data[:, : self._count]
            self._data = grown
        self._data[:, self._count : needed] = rows
        self._count = needed

    def column(self, name: str) -> np.ndarray:
        return self._data[COLUMN_INDEX[name], : self._count]


def _row(sample: Sample, origin: np.datetime64) -> list[float]:
    hours = (sample.timestamp - origin) / np.timedelta64(1, "h")
    return [
        hours,
        sample.power_measured,
        sample.power_predicted,
        sample.deviation_pct,
        sample.measured_irradiance,
        sample.measured_temperature,
    ]


class KpiTile(QFrame):
    """A headline number with its caption. A tile can be tinted, as the State tile is."""

    def __init__(self, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._colour: str | None = None
        self._value = QLabel(PLACEHOLDER)
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._value.font()
        font.setBold(True)
        self._value.setFont(font)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(caption), alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value)

    def text(self) -> str:
        return self._value.text()

    def colour(self) -> str | None:
        return self._colour

    def set_value(self, text: str, colour: str | None = None, text_colour: str = "#000000") -> None:
        self._colour = colour
        self._value.setText(text)
        style = f"background-color: {colour}; color: {text_colour};" if colour else ""
        self._value.setStyleSheet(style)


class Dashboard(QMainWindow):
    """The read-only Dashboard. Built from the run's history, then kept current from the DataBus."""

    def __init__(
        self,
        history: RunHistory,
        bus: DataBus,
        thresholds: Thresholds,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PV Digital Twin Dashboard")
        self._history = history
        self._thresholds = thresholds
        self._band_items: list[pg.LinearRegionItem] = []
        self._columns = SampleColumns()
        self._samples_shown = 0
        self._events_shown = 0
        self._dirty = True

        self.tiles = {
            "p_measured": KpiTile("P measured"),
            "p_predicted": KpiTile("P predicted"),
            "deviation": KpiTile("Deviation"),
            "state": KpiTile("State"),
            "energy": KpiTile("Energy"),
        }
        self.event_list = QListWidget()
        self.event_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._build_charts()
        self._build_layout()
        self._show_kpis(None, 0.0)

        bus.sample.connect(self._mark_dirty)
        bus.event.connect(self._mark_dirty)
        bus.run_reset.connect(self._on_reset)
        self._timer = QTimer(self)
        self._timer.setInterval(UI_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    @property
    def thresholds(self) -> Thresholds:
        """The limits the deviation bands are drawn at."""
        return self._thresholds

    def set_thresholds(self, thresholds: Thresholds) -> None:
        """Redraw the deviation bands at new limits. The plotted run is unchanged."""
        for item in self._band_items:
            self.deviation_plot.removeItem(item)
        self._thresholds = thresholds
        self._add_bands(self.deviation_plot)

    def refresh(self) -> None:
        """The UI tick: plot the Samples and list the Events that arrived since the last tick.

        Does nothing while the window is hidden or when nothing is new.
        """
        if not self._dirty or not self.isVisible():
            return
        self._dirty = False
        new_samples = self._history.samples_from(self._samples_shown)
        if new_samples:
            self._columns.append(new_samples, self._history.origin)
            self._samples_shown += len(new_samples)
            self._plot_columns()
            self._show_kpis(self._history.latest, self._history.energy_wh)
        for event in self._history.events_from(self._events_shown):
            self.event_list.insertItem(0, format_event(event))  # newest first
            self._events_shown += 1

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._dirty = True  # catch up with the run, which may have moved on while hidden
        self.refresh()

    def _mark_dirty(self, *_args) -> None:
        self._dirty = True

    def _on_reset(self) -> None:
        self._columns.clear()
        self._samples_shown = 0
        self._events_shown = 0
        self.event_list.clear()
        self._plot_columns()
        self._show_kpis(None, 0.0)
        self._dirty = True

    def _show_kpis(self, latest: Sample | None, energy_wh: float) -> None:
        if latest is None:
            for tile in self.tiles.values():
                tile.set_value(PLACEHOLDER)
            return
        readings = format_readings(latest)
        self.tiles["p_measured"].set_value(readings["P"])
        self.tiles["p_predicted"].set_value(readings["P_pred"])
        self.tiles["deviation"].set_value(f"{latest.deviation_pct:+.1f} %")
        self.tiles["energy"].set_value(f"{energy_wh:.1f} Wh")
        self.tiles["state"].set_value(
            latest.state.value, STATE_COLOURS[latest.state], STATE_TEXT_COLOURS[latest.state]
        )

    def _plot_columns(self) -> None:
        """Hand each curve its full column once per tick: one setData per curve."""
        hours = self._columns.column("hours")
        self._power_measured.setData(hours, self._columns.column("power_measured"))
        self._power_predicted.setData(hours, self._columns.column("power_predicted"))
        self._deviation.setData(hours, self._columns.column("deviation"))
        self._irradiance.setData(hours, self._columns.column("irradiance"))
        self._temperature.setData(hours, self._columns.column("temperature"))

    def _build_charts(self) -> None:
        self.power_plot = _chart("Power (W)")
        self._power_measured = self.power_plot.plot(
            pen=pg.mkPen(MEASURED_COLOUR, width=2), name="P measured"
        )
        self._power_predicted = self.power_plot.plot(
            pen=pg.mkPen(PREDICTED_COLOUR, width=2, style=Qt.PenStyle.DashLine),
            name="P predicted",
        )

        self.deviation_plot = _chart("Deviation (%)")
        self._deviation = self.deviation_plot.plot(
            pen=pg.mkPen(DEVIATION_COLOUR, width=2), name="Deviation"
        )
        self._add_bands(self.deviation_plot)

        self.irradiance_plot = _chart("G (W/m²)")
        self._irradiance = self.irradiance_plot.plot(
            pen=pg.mkPen(IRRADIANCE_COLOUR, width=2), name="G"
        )
        self.temperature_plot = _chart("T (°C)")
        self.temperature_plot.setXLink(self.irradiance_plot)
        self._temperature = self.temperature_plot.plot(
            pen=pg.mkPen(TEMPERATURE_COLOUR, width=2), name="T"
        )

    def _add_bands(self, plot: pg.PlotWidget) -> None:
        """Shade the Normal, Warning and Abnormal bands on both sides of zero, at the thresholds."""
        warning = self._thresholds.warning_pct
        abnormal = self._thresholds.abnormal_pct
        scale = GAUGE_SCALE_FACTOR * abnormal
        bands = [
            (-warning, warning, State.NORMAL),
            (warning, abnormal, State.WARNING),
            (-abnormal, -warning, State.WARNING),
            (abnormal, scale, State.ABNORMAL),
            (-scale, -abnormal, State.ABNORMAL),
        ]
        for low, high, state in bands:
            colour = QColor(STATE_COLOURS[state])
            colour.setAlphaF(BAND_ALPHA)
            region = pg.LinearRegionItem(
                values=(low, high),
                orientation="horizontal",
                brush=pg.mkBrush(colour),
                movable=False,
            )
            region.setZValue(-10)
            plot.addItem(region)
            self._band_items.append(region)

    def _build_layout(self) -> None:
        tiles = QGridLayout()
        for column, tile in enumerate(self.tiles.values()):
            tiles.addWidget(tile, 0, column)

        power_box = _framed("Measured vs predicted power", self.power_plot)
        deviation_box = _framed("Power deviation", self.deviation_plot)
        irradiance_box = QGroupBox("Irradiance and temperature")
        irradiance_layout = QVBoxLayout(irradiance_box)
        irradiance_layout.addWidget(self.irradiance_plot)
        irradiance_layout.addWidget(self.temperature_plot)
        events_box = QGroupBox("Latest events")
        events_layout = QVBoxLayout(events_box)
        events_layout.addWidget(self.event_list)

        charts = QGridLayout()
        charts.addWidget(power_box, 0, 0)
        charts.addWidget(deviation_box, 0, 1)
        charts.addWidget(irradiance_box, 1, 0)
        charts.addWidget(events_box, 1, 1)
        charts.setRowStretch(0, 1)
        charts.setRowStretch(1, 1)
        charts.setColumnStretch(0, 1)
        charts.setColumnStretch(1, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(tiles)
        layout.addLayout(charts, 1)
        self.setCentralWidget(central)


def _chart(left_label: str) -> pg.PlotWidget:
    plot = pg.PlotWidget()
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.setLabel("left", left_label)
    plot.setLabel("bottom", TIME_LABEL)
    plot.addLegend()
    return plot


def _framed(title: str, plot: pg.PlotWidget) -> QGroupBox:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.addWidget(plot)
    return box
