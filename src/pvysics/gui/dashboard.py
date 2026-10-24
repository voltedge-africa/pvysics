"""The Dashboard window: read-only analytics on the session's run, shared with the HMI.

Headline figures (drawn in QML) sit on top. Below them each chart is a dock widget: drag one to rearrange,
float it, tab it with another, or close it and bring it back from View > Panels. Charts take their colours
from the theme and follow it when it changes. The Dashboard has no controls that change the run; it
subscribes to the DataBus for new data and reads the run's history on each UI tick. Plots are updated once
per tick, with only the Samples that arrived since the last tick appended, so a full day stays responsive.
The Validation tab runs its own headless batch on the applied config and never changes or restarts the run.
With no HMI open and no Sample yet, the Overview shows an idle message and a button that opens the HMI.
"""

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QDockWidget,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pvysics.gui.alarm_panel import AlarmPanel
from pvysics.gui.log_pane import popup_log_pane
from pvysics.gui.live_charts import LiveCharts
from pvysics.gui.palette import STATE_COLOURS, STATE_TEXT_COLOURS, Palette
from pvysics.gui.metric_strip import GAUGE_SCALE_FACTOR, Group, MetricStrip, Tile
from pvysics.gui.process_view import format_readings
from pvysics.gui.ui_helpers import CompactPlot, pane
from pvysics.gui.theme import ThemeMenu, style_plot
from pvysics.gui.sample_columns import SampleColumns
from pvysics.gui.validation_view import ValidationView
from pvysics.run import Event, RunConfig, Sample, State, Thresholds

if TYPE_CHECKING:
    from pvysics.gui.session import Session

log = logging.getLogger(__name__)

UI_INTERVAL_MS = 100  # the Dashboard refreshes at most this often
IDLE_MESSAGE = "No run in progress."
BAND_ALPHA = 0.35
TIME_LABEL = "Time since start (h)"
def format_event(event: Event) -> str:
    stamp = np.datetime_as_string(event.timestamp, unit="m").split("T")[1]
    label = "State" if event.kind == "state" else "Fault"
    return f"{stamp}  {label}: {event.detail}"


class Dashboard(QMainWindow):
    """The read-only Dashboard. Built from the session's history, then kept current from its DataBus."""

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin Dashboard")
        self._session = session
        self._history = session.history
        self._theme = session.theme
        self._thresholds = session.config.thresholds
        self.validation = ValidationView(session.config, palette=session.theme.palette)
        self._band_items: list[pg.LinearRegionItem] = []
        self._columns = SampleColumns()
        self._samples_shown = 0
        self._events_shown = 0
        self._dirty = True

        self.strip = MetricStrip(
            [
                Group(
                    "Twin against plant",
                    [
                        Tile("p_predicted", "Predicted power"),
                        Tile("deviation", "Deviation"),
                        Tile("state", "State"),
                        Tile("energy", "Energy today"),
                    ],
                    spread=True,
                )
            ],
            self._theme.palette,
        )
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
        self.open_sensors_action = QAction("Open Sensors", self)
        self.open_sensors_action.triggered.connect(self._on_open_sensors)
        window_menu.addAction(self.open_sensors_action)
        self.theme_menu = ThemeMenu(self, self._theme)
        self.theme_menu.add_action(self.log_pane.view_action)
        self.theme_menu.add_actions([dock.toggleViewAction() for dock in self.docks.values()], "Panels")
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

    def _on_open_sensors(self, *_args) -> None:
        self._session.open_sensors()


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
        for plot in (self.power_plot, self.deviation_plot):
            style_plot(plot, palette)
        self.live.apply_palette(palette)
        self.strip.set_palette(palette)
        self.validation.strip.set_palette(palette)
        self._power_measured.setPen(pg.mkPen(palette.measured, width=2))
        self._power_predicted.setPen(pg.mkPen(palette.predicted, width=2, style=Qt.PenStyle.DashLine))
        self._deviation.setPen(pg.mkPen(palette.deviation, width=2))

    def _show_kpis(self, latest: Sample | None, energy_wh: float) -> None:
        if latest is None:
            self.strip.clear()
            return
        readings = format_readings(latest)
        self.strip.set_values(
            {
                "p_predicted": readings["P_pred"],
                "deviation": f"{latest.deviation_pct:+.1f} %",
                "energy": f"{energy_wh:.1f} Wh",
            }
        )
        self.strip.set_value("state", latest.state.value, STATE_COLOURS[latest.state], STATE_TEXT_COLOURS[latest.state])

    def _plot_columns(self) -> None:
        """Hand each curve its full column once per tick: one setData per curve."""
        hours = self._columns.column("hours")
        self._power_measured.setData(hours, self._columns.column("power_measured"))
        self._power_predicted.setData(hours, self._columns.column("power_predicted"))
        self._deviation.setData(hours, self._columns.column("deviation"))

    def _build_charts(self) -> None:
        self.power_plot = _chart("Power (W)")
        self._power_measured = self.power_plot.plot(name="P measured")
        self._power_predicted = self.power_plot.plot(name="P predicted")

        self.deviation_plot = _chart("Deviation (%)")
        self._deviation = self.deviation_plot.plot(name="Deviation")
        self._add_bands(self.deviation_plot)


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
        # Every chart is a dock. Power against the twin and the deviation lead; below are the curves and, tabbed
        # together, the energy, the distribution, the time in each state and the events. The plant's own sensor
        # channels (irradiance, temperature, voltage, current) are in the Sensors window.
        live = self.live
        self.charts = QMainWindow()
        self.charts.setDockNestingEnabled(True)
        self.charts.setCentralWidget(None)
        self.charts.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)
        self.docks = {
            "power": _dock("Power", self.power_plot),
            "deviation": _dock("Deviation", self.deviation_plot),
            "curves": _dock("I-V and P-V", live.curves_box),
            "energy": _dock("Energy", live.energy_box),
            "histogram": _dock("Spread", live.histogram_box),
            "states": _dock("States", live.states_box),
            "events": _dock("Events", self.event_list),
        }
        docks = self.docks
        self.charts.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, docks["power"])
        self.charts.splitDockWidget(docks["power"], docks["deviation"], Qt.Orientation.Horizontal)
        self.charts.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, docks["curves"])
        self.charts.splitDockWidget(docks["curves"], docks["energy"], Qt.Orientation.Horizontal)
        for key in ("histogram", "states", "events"):
            self.charts.tabifyDockWidget(docks["energy"], docks[key])
        docks["energy"].raise_()
        self.charts.resizeDocks([docks["power"], docks["deviation"]], [3, 2], Qt.Orientation.Horizontal)
        self.charts.resizeDocks([docks["curves"], docks["energy"]], [3, 2], Qt.Orientation.Horizontal)

        self.overview = QWidget()
        layout = QVBoxLayout(self.overview)
        layout.setSpacing(8)
        layout.addWidget(self.strip)
        layout.addWidget(self.charts, 1)
        self._idle_page, self.idle_message, self.open_hmi_button = self._build_idle_page()
        self._pages = QStackedWidget()
        self._pages.addWidget(self._idle_page)
        self._pages.addWidget(self.overview)

        tabs = QTabWidget()
        tabs.addTab(self._pages, "Overview")
        self.alarm_panel = AlarmPanel(self._session.alarms)
        tabs.addTab(self.alarm_panel, "Alarms")
        tabs.addTab(self.validation, "Validation")
        self.setCentralWidget(tabs)
        self.log_pane = popup_log_pane(self, self._session.log_bridge, self._theme)

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


def _dock(title: str, widget: QWidget) -> QDockWidget:
    """A chart as a dock: movable, floatable and closable, with its title in a flat title bar."""
    dock = QDockWidget(title)
    dock.setObjectName(f"dock_{title}")
    dock.setWidget(pane(widget))
    return dock
