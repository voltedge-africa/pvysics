"""The Sensors window: the plant's own measurements, apart from the twin.

Irradiance, module temperature, voltage, current and measured power are what a real plant's sensors would
report. They live in a window of their own so that, when hardware feeds are added, this is the one place they
connect: today the source is the simulated plant, and the header says so. The Setup tab sets up the simulated plant and the source. The figures and charts read the
session's history exactly as the Dashboard does, so a hardware feed that fills the history would appear here
with no other change. Each chart is a dock, and charts take their colours from the theme.
"""

import logging
from typing import TYPE_CHECKING

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QDockWidget, QHBoxLayout, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from pvysics.gui.live_charts import _time_plot
from pvysics.gui.log_pane import popup_log_pane
from pvysics.gui.metric_strip import Group, MetricStrip, Tile
from pvysics.gui.palette import Palette
from pvysics.gui.process_view import format_readings
from pvysics.gui.sample_columns import SampleColumns
from pvysics.gui.sensor_setup import SensorSetupView
from pvysics.gui.theme import ThemeMenu, style_plot
from pvysics.gui.ui_helpers import pane, role_label
from pvysics.run import Sample

if TYPE_CHECKING:
    from pvysics.gui.session import Session

log = logging.getLogger(__name__)

UI_INTERVAL_MS = 100  # the window refreshes at most this often
SOURCE_SIMULATED = "Simulated plant"
HARDWARE_NOT_CONNECTED = "Hardware feed: not connected"
PLOT_MIN_HEIGHT_PX = 120
AXIS_WIDTH_PX = 56
READING_KEYS = ("G", "T", "V", "I", "P")


class SensorsWindow(QMainWindow):
    """The plant's sensor channels: five figures and four charts, read from the session's history."""

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin Sensors")
        self.resize(1100, 720)
        self._session = session
        self._history = session.history
        self._theme = session.theme
        self._columns = SampleColumns()
        self._samples_shown = 0
        self._dirty = True

        self.strip = MetricStrip(
            [
                Group(
                    "Plant sensors",
                    [
                        Tile("G", "Irradiance"),
                        Tile("T", "Module temperature"),
                        Tile("V", "Voltage"),
                        Tile("I", "Current"),
                        Tile("P", "Measured power"),
                    ],
                    spread=True,
                )
            ],
            self._theme.palette,
        )
        self.source_label = role_label(SOURCE_SIMULATED, "strong")
        self.hardware_label = role_label(HARDWARE_NOT_CONNECTED, "muted")
        self._build_charts()
        self._build_layout()
        self.log_pane = popup_log_pane(self, session.log_bridge, self._theme)

        window_menu = self.menuBar().addMenu("&Window")
        self.open_hmi_action = QAction("Open HMI", self)
        self.open_hmi_action.triggered.connect(self._on_open_hmi)
        window_menu.addAction(self.open_hmi_action)
        self.open_dashboard_action = QAction("Open Dashboard", self)
        self.open_dashboard_action.triggered.connect(self._on_open_dashboard)
        window_menu.addAction(self.open_dashboard_action)
        self.theme_menu = ThemeMenu(self, self._theme)
        self.theme_menu.add_action(self.log_pane.view_action)
        self.theme_menu.add_actions([dock.toggleViewAction() for dock in self.docks.values()], "Panels")
        self._theme.changed.connect(self._apply_palette)
        self._apply_palette(self._theme.palette)

        bus = session.bus
        bus.sample.connect(self._mark_dirty)
        bus.run_reset.connect(self._on_reset)
        self._timer = QTimer(self)
        self._timer.setInterval(UI_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    def refresh(self) -> None:
        """The UI tick: plot the Samples that arrived since the last tick. Does nothing while hidden."""
        if not self.isVisible() or not self._dirty:
            return
        self._dirty = False
        new_samples = self._history.samples_from(self._samples_shown)
        if not new_samples:
            return
        energies = self._history.energies_from(self._samples_shown)
        self._columns.append(new_samples, self._history.origin, energies)
        self._samples_shown += len(new_samples)
        self._plot_columns()
        self._show_readings(new_samples[-1])

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._dirty = True  # catch up with the run, which may have moved on while hidden
        self.refresh()

    def _mark_dirty(self, *_args) -> None:
        self._dirty = True

    def _on_reset(self) -> None:
        self._columns.clear()
        self._samples_shown = 0
        self._plot_columns()
        self.strip.clear()
        self._dirty = True

    def _show_readings(self, sample: Sample) -> None:
        readings = format_readings(sample)
        self.strip.set_values({key: readings[key] for key in READING_KEYS})

    def _plot_columns(self) -> None:
        hours = self._columns.column("hours")
        for curve, column in self._curves.items():
            curve.setData(hours, self._columns.column(column))

    def _apply_palette(self, palette: Palette) -> None:
        for plot in self._plots:
            style_plot(plot, palette)
        self.strip.set_palette(palette)
        for curve, colour in zip(self._curves, (palette.irradiance, palette.temperature, palette.voltage, palette.current)):
            curve.setPen(pg.mkPen(colour, width=2))

    def _build_charts(self) -> None:
        specs = (
            ("irradiance", "Irradiance (W/m²)"),
            ("temperature", "Module temperature (°C)"),
            ("voltage", "Voltage (V)"),
            ("current", "Current (A)"),
        )
        self.plots: dict[str, pg.PlotWidget] = {}
        self._curves: dict[pg.PlotDataItem, str] = {}
        for column, label in specs:
            plot = _time_plot(label, PLOT_MIN_HEIGHT_PX)
            plot.getAxis("left").setWidth(AXIS_WIDTH_PX)
            self.plots[column] = plot
            self._curves[plot.plot()] = column
        self._plots = list(self.plots.values())

    def _build_layout(self) -> None:
        self.charts = QMainWindow()
        self.charts.setDockNestingEnabled(True)
        self.charts.setCentralWidget(None)
        self.charts.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)
        titles = {
            "irradiance": "Irradiance",
            "temperature": "Module temperature",
            "voltage": "Voltage",
            "current": "Current",
        }
        self.docks = {key: _dock(titles[key], self.plots[key]) for key in titles}
        d = self.docks
        # Irradiance and temperature are the conditions, so they share a pane as tabs; voltage and current are the
        # electrical output, and share the row below.
        self.charts.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, d["irradiance"])
        self.charts.tabifyDockWidget(d["irradiance"], d["temperature"])
        d["irradiance"].raise_()
        self.charts.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, d["voltage"])
        self.charts.splitDockWidget(d["voltage"], d["current"], Qt.Orientation.Horizontal)

        header = QHBoxLayout()
        header.addWidget(self.source_label)
        header.addStretch(1)
        header.addWidget(self.hardware_label)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self.strip)
        layout.addWidget(self.charts, 1)
        self.setup_view = SensorSetupView(self._session)
        self.setup_view.connection_changed.connect(self._on_connection_changed)
        self.tabs = QTabWidget()
        self.tabs.addTab(body, "Live")
        self.tabs.addTab(self.setup_view, "Setup")
        self.setCentralWidget(self.tabs)

    def _on_connection_changed(self, text: str) -> None:
        self.hardware_label.setText(text or HARDWARE_NOT_CONNECTED)

    def _on_open_hmi(self, *_args) -> None:
        self._session.open_hmi()

    def _on_open_dashboard(self, *_args) -> None:
        self._session.open_dashboard()


def _dock(title: str, widget: QWidget) -> QDockWidget:
    dock = QDockWidget(title)
    dock.setObjectName(f"dock_{title}")
    dock.setWidget(pane(widget))
    return dock
