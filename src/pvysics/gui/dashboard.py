"""The Dashboard window: read-only analytics on the session's run, shared with the HMI.

Layout follows the dashboard wireframe: KPI tiles on top, measured vs predicted power and
the deviation chart in the middle, irradiance and temperature with the event log below. Charts take
their colours from the theme, and follow it when the theme changes.
The Dashboard has no controls that change the run; it subscribes to the DataBus for new data
and reads the run's history on each UI tick. Plots are updated once per tick, with only the
Samples that arrived since the last tick appended, so a full day stays responsive.
The Overview tab holds the live view. The Live charts tab holds five more live views (live_charts.py).
The Validation tab runs its own headless batch on the
applied config and never changes or restarts the run. With no HMI open and no Sample yet, the
Overview and Live charts tabs show an idle message and a button that opens the HMI.
"""

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pvysics.gui.log_pane import bottom_log_pane
from pvysics.gui.live_charts import LiveCharts
from pvysics.gui.palette import STATE_COLOURS, STATE_TEXT_COLOURS, Palette
from pvysics.gui.process_view import GAUGE_SCALE_FACTOR, PLACEHOLDER, format_readings
from pvysics.gui.ui_helpers import CompactPlot
from pvysics.gui.theme import ThemeMenu, style_plot
from pvysics.gui.validation_view import ValidationView
from pvysics.gui.widgets import KpiTile
from pvysics.run import Event, RunConfig, Sample, State, Thresholds

if TYPE_CHECKING:
    from pvysics.gui.session import Session

log = logging.getLogger(__name__)

UI_INTERVAL_MS = 100  # the Dashboard refreshes at most this often
IDLE_MESSAGE = "No run in progress. Start a run from the HMI."
BAND_ALPHA = 0.35
CARD_COLUMNS = 3
CARD_ROWS = 4
CARD_MIN_HEIGHT_PX = 250  # a card is never shorter, so its axes stay legible; the Overview scrolls instead
TIME_LABEL = "Time since start (h)"
COLUMNS = (
    "hours",
    "power_measured",
    "power_predicted",
    "deviation",
    "irradiance",
    "temperature",
    "voltage",
    "current",
    "energy_wh",
)
COLUMN_INDEX = {name: index for index, name in enumerate(COLUMNS)}
INITIAL_CAPACITY = 1024


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

    def append(self, samples: list[Sample], origin: np.datetime64, energies: list[float]) -> None:
        rows = np.array([_row(sample, origin, energy) for sample, energy in zip(samples, energies)], dtype=float).T
        needed = self._count + rows.shape[1]
        if needed > self._data.shape[1]:
            grown = np.empty((len(COLUMNS), max(needed, 2 * self._data.shape[1])))
            grown[:, : self._count] = self._data[:, : self._count]
            self._data = grown
        self._data[:, self._count : needed] = rows
        self._count = needed

    def column(self, name: str) -> np.ndarray:
        return self._data[COLUMN_INDEX[name], : self._count]


def _row(sample: Sample, origin: np.datetime64, energy_wh: float) -> list[float]:
    hours = (sample.timestamp - origin) / np.timedelta64(1, "h")
    return [
        hours,
        sample.power_measured,
        sample.power_predicted,
        sample.deviation_pct,
        sample.measured_irradiance,
        sample.measured_temperature,
        sample.measured_voltage,
        sample.measured_current,
        energy_wh,
    ]


class Dashboard(QMainWindow):
    """The read-only Dashboard. Built from the session's history, then kept current from its DataBus."""

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin Dashboard")
        self._session = session
        self._history = session.history
        self._theme = session.theme
        self._thresholds = session.config.thresholds
        self.validation = ValidationView(session.config)
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
        self._update_pages()
        window_menu = self.menuBar().addMenu("&Window")
        self.open_hmi_action = QAction("Open HMI", self)
        self.open_hmi_action.triggered.connect(self._on_open_hmi)
        window_menu.addAction(self.open_hmi_action)
        self.theme_menu = ThemeMenu(self, self._theme)
        self.theme_menu.add_action(self.log_pane.view_action)
        self._theme.changed.connect(self._apply_palette)
        self._apply_palette(self._theme.palette)

        bus = session.bus
        bus.sample.connect(self._mark_dirty)
        bus.event.connect(self._mark_dirty)
        bus.run_reset.connect(self._on_reset)
        session.config_changed.connect(self.set_config)
        self._timer = QTimer(self)
        self._timer.setInterval(UI_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    @property
    def thresholds(self) -> Thresholds:
        """The limits the deviation bands are drawn at."""
        return self._thresholds

    def set_config(self, config: RunConfig) -> None:
        """Follow the applied config: redraw the deviation bands and validate this config next.

        The plotted run is unchanged; a new run arrives through the bus.
        """
        for item in self._band_items:
            self.deviation_plot.removeItem(item)
        self._thresholds = config.thresholds
        self._add_bands(self.deviation_plot)
        self.live.set_datasheet(config.datasheet)
        self.validation.set_config(config)

    def closeEvent(self, event) -> None:
        log.debug("Window closed: Dashboard")
        self.validation.shutdown()  # a running validation ends before the window closes
        super().closeEvent(event)

    def refresh(self) -> None:
        """The UI tick: plot the Samples and list the Events that arrived since the last tick.

        Does nothing while the window is hidden or when nothing is new.
        """
        if not self.isVisible():
            return
        self._update_pages()
        if not self._dirty:
            return
        self._dirty = False
        new_samples = self._history.samples_from(self._samples_shown)
        if new_samples:
            energies = self._history.energies_from(self._samples_shown)
            self._columns.append(new_samples, self._history.origin, energies)
            self._samples_shown += len(new_samples)
            self._plot_columns()
            self.live.update(self._columns, new_samples)
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

    def _update_pages(self) -> None:
        """The idle message while no HMI is open and no Sample has arrived; the charts otherwise."""
        idle = not self._session.hmi_open and self._history.sample_count == 0
        self._pages.setCurrentWidget(self._idle_page if idle else self.overview)

    def _on_open_hmi(self, *_args) -> None:
        self._session.open_hmi()


    def _on_reset(self) -> None:
        self._columns.clear()
        self._samples_shown = 0
        self._events_shown = 0
        self.event_list.clear()
        self._plot_columns()
        self.live.clear()
        self._show_kpis(None, 0.0)
        self._dirty = True

    def _apply_palette(self, palette: Palette) -> None:
        """Restyle the charts and their curves for a palette. Runs at start and on each theme change."""
        for plot in (self.power_plot, self.deviation_plot, self.irradiance_plot, self.temperature_plot):
            style_plot(plot, palette)
        self.live.apply_palette(palette)
        self._power_measured.setPen(pg.mkPen(palette.measured, width=2))
        self._power_predicted.setPen(pg.mkPen(palette.predicted, width=2, style=Qt.PenStyle.DashLine))
        self._deviation.setPen(pg.mkPen(palette.deviation, width=2))
        self._irradiance.setPen(pg.mkPen(palette.irradiance, width=2))
        self._temperature.setPen(pg.mkPen(palette.temperature, width=2))

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
        self._power_measured = self.power_plot.plot(name="P measured")
        self._power_predicted = self.power_plot.plot(name="P predicted")

        self.deviation_plot = _chart("Deviation (%)")
        self._deviation = self.deviation_plot.plot(name="Deviation")
        self._add_bands(self.deviation_plot)

        self.irradiance_plot = _chart("G (W/m²)")
        self._irradiance = self.irradiance_plot.plot(name="G")
        self.temperature_plot = _chart("T (°C)")
        self.temperature_plot.setXLink(self.irradiance_plot)
        self._temperature = self.temperature_plot.plot(name="T")

        self.live = LiveCharts(self._session.config.datasheet, self._theme.palette, own_layout=False)

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

        # One grid of cards, most telling first: power against the twin and the deviation, then the
        # conditions behind them, then the electrical detail, then the distributions and the event log.
        live = self.live
        charts = QGridLayout()
        charts.addWidget(power_box, 0, 0, 1, 2)
        charts.addWidget(deviation_box, 0, 2)
        charts.addWidget(irradiance_box, 1, 0)
        charts.addWidget(live.voltage_current_box, 1, 1)
        charts.addWidget(live.energy_box, 1, 2)
        charts.addWidget(live.curves_box, 2, 0, 1, 2)
        charts.addWidget(live.states_box, 2, 2)
        charts.addWidget(live.histogram_box, 3, 0)
        charts.addWidget(events_box, 3, 1, 1, 2)
        for column in range(CARD_COLUMNS):
            charts.setColumnStretch(column, 1)
        for row in range(CARD_ROWS):
            charts.setRowMinimumHeight(row, CARD_MIN_HEIGHT_PX)
            charts.setRowStretch(row, 1)
        body = QWidget()
        body.setLayout(charts)
        # The cards scroll, so a short window shows the first rows and the rest a scroll away; the KPI row stays put.
        self.overview_scroll = QScrollArea()
        self.overview_scroll.setWidgetResizable(True)
        self.overview_scroll.setWidget(body)

        self.overview = QWidget()
        layout = QVBoxLayout(self.overview)
        layout.addLayout(tiles)
        layout.addWidget(self.overview_scroll, 1)
        self._idle_page, self.idle_message, self.open_hmi_button = self._build_idle_page()
        self._pages = QStackedWidget()
        self._pages.addWidget(self._idle_page)
        self._pages.addWidget(self.overview)

        tabs = QTabWidget()
        tabs.addTab(self._pages, "Overview")
        tabs.addTab(self.validation, "Validation")
        self.setCentralWidget(tabs)
        self.log_pane = bottom_log_pane(self, self._session.log_bridge, self._theme)

    def _build_idle_page(self) -> tuple[QWidget, QLabel, QPushButton]:
        """The page shown while no run is in progress: the message, and a button that opens the HMI."""
        message = QLabel(IDLE_MESSAGE)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        button = QPushButton("Open HMI")
        button.clicked.connect(self._on_open_hmi)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        layout.addWidget(message)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        return page, message, button


def _chart(left_label: str) -> pg.PlotWidget:
    plot = CompactPlot()
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
