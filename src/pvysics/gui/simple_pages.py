"""The pages of the simple window. Each is a view on the session's one run, built from the existing widgets.

Dashboard is the home page: the run controls, six readings, the power chart and the deviation card. Analysis holds
the Dataset Analysis view by default (imported measurements scored by the twin, replayed on the Dashboard) with the
Validation view beside it; SDM Model and Settings wrap the Model and Setup views the advanced version uses. Trends
charts the five sensor channels, Data lists every sample, and Event Log lists alarms, state changes and fault
injections. Pages take their colours from the palette, so they follow the theme the session holds.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pvysics.export import write_samples_csv
from pvysics.gui.alarm_panel import AlarmPanel
from pvysics.gui.dashboard import format_event
from pvysics.gui.dataset_view import DatasetAnalysisView
from pvysics.gui.live_controller import FeedStatus
from pvysics.gui.live_charts import _time_plot
from pvysics.gui.metric_strip import split_reading
from pvysics.gui.model_view import ModelView
from pvysics.gui.palette import STATE_COLOURS, Palette
from pvysics.gui.process_view import describe_state, format_number, format_readings
from pvysics.gui.run_toolbar import RunToolbar
from pvysics.gui.sample_columns import SampleColumns
from pvysics.gui.setup_view import SetupView
from pvysics.gui.theme import style_plot
from pvysics.gui.trend import PowerTrend
from pvysics.gui.ui_helpers import role_label
from pvysics.gui.validation_view import ValidationView
from pvysics.run import Event, Sample, State

if TYPE_CHECKING:
    from pvysics.gui.session import Session

log = logging.getLogger(__name__)

UI_INTERVAL_MS = 100  # the pages that redraw on a timer do so at most this often
EMPTY = "--"
WAITING = "WAITING"
SOURCE_CHIP = "SOURCE: SIMULATED PLANT"
PAGE_MARGIN_PX = 20
GAP_PX = 14
TREND_MIN_HEIGHT_PX = 150
TABLE_PADDING_PX = 28  # a column is as wide as its header, or its longest cell, plus this
MAX_TABLE_ROWS = 1000  # the Data page shows the newest rows; the export has them all


def card(*children: QWidget | QHBoxLayout | QVBoxLayout | None) -> QFrame:
    """A boxed panel holding the given widgets or layouts, top to bottom. None is a stretch that takes the spare height."""
    frame = QFrame()
    frame.setProperty("card", "true")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(8)
    for child in children:
        if child is None:
            layout.addStretch(1)
        elif isinstance(child, QWidget):
            layout.addWidget(child)
        else:
            layout.addLayout(child)
    return frame


def card_header(title: str, subtitle: str = "", *actions: QWidget) -> QHBoxLayout:
    """A card's title in capitals with a muted line under it, and any action buttons at the right."""
    row = QHBoxLayout()
    text = QVBoxLayout()
    text.setSpacing(2)
    text.addWidget(role_label(title.upper(), "cardTitle"))
    if subtitle:
        text.addWidget(role_label(subtitle, "cardSub"))
    row.addLayout(text)
    row.addStretch(1)
    for action in actions:
        row.addWidget(action)
    return row


def page_header(title: str, subtitle: str, *right: QWidget) -> QHBoxLayout:
    """A page's large title and a muted line under it, with chips or buttons at the right."""
    row = QHBoxLayout()
    text = QVBoxLayout()
    text.setSpacing(2)
    text.addWidget(role_label(title, "pageTitle"))
    text.addWidget(role_label(subtitle, "pageSub"))
    row.addLayout(text)
    row.addStretch(1)
    for widget in right:
        row.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)
    return row


def page_layout(page: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(page)
    layout.setContentsMargins(PAGE_MARGIN_PX, PAGE_MARGIN_PX, PAGE_MARGIN_PX, PAGE_MARGIN_PX)
    layout.setSpacing(GAP_PX)
    return layout


def colour_text(label: QLabel, colour: str | None) -> None:
    """Colour a label's text, or give it back the stylesheet's colour with None."""
    label.setStyleSheet("" if colour is None else f"color: {colour};")


class KpiCard(QFrame):
    """One reading: its title in capitals, the figure large and its unit beside it. Dashes until there is a value."""

    def __init__(self, title: str, unit: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", "true")
        self._unit = unit
        self.value_label = role_label(EMPTY, "kpi")
        self.unit_label = role_label(unit, "kpiUnit")
        row = QHBoxLayout()
        row.addWidget(self.value_label)
        row.addWidget(self.unit_label, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        layout.addWidget(role_label(title.upper(), "cardSub"))
        layout.addLayout(row)

    @property
    def text(self) -> str:
        return self.value_label.text()

    def set_reading(self, reading: str) -> None:
        """Show a reading such as "412 W/m²": the number large, the unit beside it."""
        number, unit = split_reading(reading)
        self.value_label.setText(number)
        self.unit_label.setText(unit or self._unit)

    def set_text(self, text: str) -> None:
        self.value_label.setText(text)

    def clear(self) -> None:
        self.value_label.setText(EMPTY)
        self.unit_label.setText(self._unit)


class DashboardPage(QWidget):
    """The home page: run controls, six readings, the power chart and the deviation with its state."""

    event_log_requested = pyqtSignal()

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self._session = session
        self._history = session.history
        self._peak_w = 0.0
        self.toolbar = RunToolbar(session.playback, session.bus, live=session.live)
        self.source_chip = role_label(f"●  {SOURCE_CHIP}", "chip")
        self.state_chip = role_label(f"SYSTEM STATE: {WAITING}", "chip")

        self.kpis = {
            "V": KpiCard("Voltage", "V"),
            "I": KpiCard("Current", "A"),
            "P": KpiCard("Measured power", "W"),
            "P_pred": KpiCard("Predicted power", "W"),
            "G": KpiCard("Irradiance", "W/m²"),
            "T": KpiCard("Module temperature", "°C"),
        }
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(GAP_PX)
        for kpi in self.kpis.values():
            kpi_row.addWidget(kpi, 1)

        self.trend = PowerTrend(session.theme.palette)
        self.save_button = QPushButton("SAVE CHART")
        self.save_button.setToolTip("Save the chart as an image.")
        self.save_button.clicked.connect(self._on_save_clicked)
        chart_card = card(
            card_header("Measured vs predicted power", "Electrical power · P = V × I · units: W", self.save_button),
            self.trend,
        )

        self.deviation_label = role_label(EMPTY, "deviation")
        self.state_label = role_label("", "cardSub")
        self.limits_label = role_label("", "cardSub")
        self.limits_label.setWordWrap(True)
        self.tiles = {
            "peak": KpiCard("Peak power", "W"),
            "energy": KpiCard("Energy", "Wh"),
            "samples": KpiCard("Samples", ""),
            "elapsed": KpiCard("Elapsed", ""),
        }
        tile_grid = QGridLayout()
        tile_grid.setSpacing(10)
        for index, tile in enumerate(self.tiles.values()):
            tile_grid.addWidget(tile, *divmod(index, 2))
        self.event_log_button = QPushButton("OPEN EVENT LOG")
        self.event_log_button.setProperty("variant", "primary")
        self.event_log_button.clicked.connect(self._on_event_log_clicked)
        deviation_card = card(
            card_header("Power deviation"),
            self.deviation_label,
            self.state_label,
            self.limits_label,
            None,
            tile_grid,
            self.event_log_button,
        )

        layout = page_layout(self)
        layout.addLayout(page_header("PV DIGITAL TWIN", "Physics-informed PV state estimation · real-time monitoring", self.source_chip, self.state_chip))
        layout.addWidget(self.toolbar)
        layout.addLayout(kpi_row)
        body = QHBoxLayout()
        body.setSpacing(GAP_PX)
        body.addWidget(chart_card, 3)
        body.addWidget(deviation_card, 1)
        layout.addLayout(body, 1)

        bus = session.bus
        bus.sample.connect(self._show_sample)
        bus.run_reset.connect(self._show_start)
        session.config_changed.connect(self._show_limits)
        session.config_changed.connect(self._show_source)
        session.dataset_replayed.connect(self._show_dataset_source)
        session.live.active_changed.connect(self._show_live_source)
        session.live.status_changed.connect(self._show_feed_status)
        session.theme.changed.connect(self.apply_palette)
        self._show_start()  # the empty state first; a window opened mid-run then replays the run so far over it
        for sample in self._history.samples_from(0):
            self.trend.add_sample(sample)
            self._peak_w = max(self._peak_w, sample.power_measured)
        self.trend.flush()
        if self._history.latest is not None:
            self._show_sample(self._history.latest, replay=True)
        self.apply_palette(session.theme.palette)

    @property
    def state_text(self) -> str:
        return self.state_chip.text()

    def apply_palette(self, palette: Palette) -> None:
        self.trend.apply_palette(palette)
        colour_text(self.source_chip, palette.muted_text)
        latest = self._history.latest
        colour_text(self.state_chip, palette.muted_text if latest is None else STATE_COLOURS[latest.state])

    def _on_save_clicked(self, *_args) -> None:
        self.trend.plot.image_action.trigger()

    def _on_event_log_clicked(self, *_args) -> None:
        self.event_log_requested.emit()

    def _show_limits(self, *_args) -> None:
        thresholds = self._session.config.thresholds
        self.limits_label.setText(
            f"NORMAL ≤ {thresholds.warning_pct:g}% · WARNING ≤ {thresholds.abnormal_pct:g}% · "
            f"ABNORMAL > {thresholds.abnormal_pct:g}%"
        )

    def _show_source(self, *_args) -> None:
        """The simulated plant is the source again: a new config has replaced any dataset replay."""
        self.source_chip.setText(f"●  {SOURCE_CHIP}")

    def _show_dataset_source(self, name: str) -> None:
        self.source_chip.setText(f"●  SOURCE: DATASET '{name.upper()}'")

    def _show_live_source(self, active: bool) -> None:
        self.source_chip.setText("●  SOURCE: LIVE FEED" if active else "●  SOURCE: LIVE FEED (STOPPED)")

    def _show_feed_status(self, status) -> None:
        """No data for the timeout shows on the state chip. The state comes back with the next reading."""
        if status is FeedStatus.NO_DATA:
            self.state_chip.setText("SYSTEM STATE: NO DATA")
            colour_text(self.state_chip, STATE_COLOURS[State.WARNING])
        elif status is FeedStatus.RECEIVING and self._history.latest is not None:
            self._show_sample(self._history.latest, replay=True)

    def _show_start(self) -> None:
        self._peak_w = 0.0
        for kpi in (*self.kpis.values(), *self.tiles.values()):
            kpi.clear()
        self.tiles["samples"].set_text("0")
        self.tiles["energy"].set_text("0.0")
        self.tiles["elapsed"].set_text("00:00:00")
        self.deviation_label.setText(EMPTY)
        self.state_label.setText("")
        self.state_chip.setText(f"SYSTEM STATE: {WAITING}")
        colour_text(self.state_chip, self._session.theme.palette.muted_text)
        colour_text(self.deviation_label, None)
        self.trend.clear()
        self._show_limits()

    def _show_sample(self, sample: Sample, replay: bool = False) -> None:
        readings = format_readings(sample)
        for key, kpi in self.kpis.items():
            kpi.set_reading(readings[key])
        self._peak_w = max(self._peak_w, sample.power_measured)
        self.tiles["peak"].set_text(format_number(self._peak_w, 1))
        self.tiles["energy"].set_text(format_number(self._history.energy_wh, 1))
        self.tiles["samples"].set_text(str(self._history.sample_count))
        seconds = int((sample.timestamp - self._history.origin) / np.timedelta64(1, "s"))
        hours, rest = divmod(seconds, 3600)
        self.tiles["elapsed"].set_text(f"{hours:02d}:{rest // 60:02d}:{rest % 60:02d}")
        self.deviation_label.setText(f"{format_number(sample.deviation_pct, 1, signed=True)} %")
        sentence, _detail = describe_state(sample, self._session.config.thresholds)
        self.state_label.setText(sentence)
        self.state_chip.setText(f"SYSTEM STATE: {sample.state.value.upper()}")
        colour = STATE_COLOURS[sample.state]
        colour_text(self.state_chip, colour)
        colour_text(self.deviation_label, colour)
        if not replay:
            self.trend.add_sample(sample)


class TrendsPage(QWidget):
    """The five sensor channels, one chart each, read from the session's history on a timer."""

    CHANNELS = (
        ("irradiance", "Irradiance", "Irradiance (W/m²)"),
        ("temperature", "Module temperature", "Module temperature (°C)"),
        ("voltage", "Voltage", "Voltage (V)"),
        ("current", "Current", "Current (A)"),
        ("power_measured", "Measured power", "Measured power (W)"),
    )

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self._history = session.history
        self._columns = SampleColumns()
        self._samples_shown = 0
        self._dirty = True
        self.plots: dict[str, pg.PlotWidget] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}
        grid = QGridLayout()
        grid.setSpacing(GAP_PX)
        for index, (column, title, label) in enumerate(self.CHANNELS):
            plot = _time_plot(label, TREND_MIN_HEIGHT_PX)
            self.plots[column] = plot
            self._curves[column] = plot.plot()
            grid.addWidget(card(card_header(title), plot), *divmod(index, 2))
        layout = page_layout(self)
        layout.addLayout(page_header("Trends", "The plant's sensor channels over the run"))
        layout.addLayout(grid, 1)

        session.bus.sample.connect(self._mark_dirty)
        session.bus.run_reset.connect(self._on_reset)
        session.theme.changed.connect(self.apply_palette)
        self.apply_palette(session.theme.palette)
        self._timer = QTimer(self)
        self._timer.setInterval(UI_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    def refresh(self) -> None:
        """Plot the Samples that arrived since the last refresh. Does nothing while the page is hidden."""
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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._dirty = True  # catch up with the run, which moved on while the page was hidden
        self.refresh()

    def apply_palette(self, palette: Palette) -> None:
        colours = {
            "irradiance": palette.irradiance,
            "temperature": palette.temperature,
            "voltage": palette.voltage,
            "current": palette.current,
            "power_measured": palette.measured,
        }
        for column, plot in self.plots.items():
            style_plot(plot, palette)
            self._curves[column].setPen(pg.mkPen(colours[column], width=2))

    def _mark_dirty(self, *_args) -> None:
        self._dirty = True

    def _on_reset(self) -> None:
        self._columns.clear()
        self._samples_shown = 0
        self._plot_columns()
        self._dirty = True

    def _plot_columns(self) -> None:
        hours = self._columns.column("hours")
        for column, curve in self._curves.items():
            curve.setData(hours, self._columns.column(column))


class DataPage(QWidget):
    """Every sample of the run as a table, newest first, with the whole run exported as CSV."""

    HEADERS = (
        "Time",
        "Irradiance (W/m²)",
        "Temperature (°C)",
        "Voltage (V)",
        "Current (A)",
        "Measured (W)",
        "Predicted (W)",
        "Deviation (%)",
        "State",
        "Faults",
    )

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self._history = session.history
        self._samples_shown = 0
        self._dirty = True
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        metrics = self.table.fontMetrics()
        for column, header in enumerate(self.HEADERS):
            sample = "2025-01-15 09:33:00" if column == 0 else header
            self.table.setColumnWidth(column, metrics.horizontalAdvance(sample) + TABLE_PADDING_PX)
        self.export_button = QPushButton("EXPORT CSV")
        self.export_button.setProperty("variant", "primary")
        self.export_button.clicked.connect(self._on_export_clicked)
        self.status_label = role_label("", "pageSub")
        layout = page_layout(self)
        layout.addLayout(page_header("Data", "Every sample of the run: the plant's readings, the twin's prediction and the state", self.export_button))
        layout.addWidget(card(self.table, self.status_label), 1)

        session.bus.sample.connect(self._mark_dirty)
        session.bus.run_reset.connect(self._on_reset)
        self._timer = QTimer(self)
        self._timer.setInterval(UI_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    @property
    def row_count(self) -> int:
        return self.table.rowCount()

    def refresh(self) -> None:
        """Add the Samples that arrived since the last refresh, newest on top. Does nothing while the page is hidden."""
        if not self.isVisible() or not self._dirty:
            return
        self._dirty = False
        new_samples = self._history.samples_from(self._samples_shown)
        self._samples_shown += len(new_samples)
        for sample in new_samples[-MAX_TABLE_ROWS:]:
            self.table.insertRow(0)
            for column, text in enumerate(self._cells(sample)):
                self.table.setItem(0, column, QTableWidgetItem(text))
        self.table.setRowCount(min(self.table.rowCount(), MAX_TABLE_ROWS))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._dirty = True
        self.refresh()

    def export_csv(self, path: str) -> None:
        """Write every sample of the run, not only the rows shown."""
        write_samples_csv(Path(path), {"run": self._history.samples_from(0)})

    @staticmethod
    def _cells(sample: Sample) -> list[str]:
        return [
            np.datetime_as_string(sample.timestamp, unit="s").replace("T", " "),
            format_number(sample.measured_irradiance, 0),
            format_number(sample.measured_temperature, 1),
            format_number(sample.measured_voltage, 1),
            format_number(sample.measured_current, 2),
            format_number(sample.power_measured, 1),
            format_number(sample.power_predicted, 1),
            format_number(sample.deviation_pct, 1, signed=True),
            sample.state.value,
            ", ".join(kind.value for kind in sample.active_faults),
        ]

    def _mark_dirty(self, *_args) -> None:
        self._dirty = True

    def _on_reset(self) -> None:
        self.table.setRowCount(0)
        self._samples_shown = 0
        self._dirty = True

    def _on_export_clicked(self, *_args) -> None:
        path, _chosen = QFileDialog.getSaveFileName(self, "Export samples", "", "CSV file (*.csv)")
        if not path:
            return
        path = str(Path(path).with_suffix(".csv"))
        try:
            self.export_csv(path)
        except OSError as error:
            log.error("Export failed: could not write %s: %s", Path(path).name, error)
            self.status_label.setText(f"Could not write {Path(path).name}: {error}")
        else:
            self.status_label.setText(f"Samples written to {path}.")


class EventLogPage(QWidget):
    """The alarms (with Acknowledge) and the list of state changes and fault injections, newest first."""

    log_requested = pyqtSignal()

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self._history = session.history
        self.alarm_panel = AlarmPanel(session.alarms)
        self.event_list = QListWidget()
        self.event_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.log_button = QPushButton("SHOW LOG")
        self.log_button.setToolTip("Open the application log (Ctrl+L).")
        self.log_button.clicked.connect(self._on_log_clicked)
        layout = page_layout(self)
        layout.addLayout(page_header("Event Log", "Alarms, state changes and injected faults", self.log_button))
        layout.addWidget(card(card_header("Alarms", "Acknowledge an alarm to mark it as seen."), self.alarm_panel), 1)
        layout.addWidget(card(card_header("Events", "State changes and fault injections"), self.event_list), 1)

        for event in reversed(self._history.events_from(0)):
            self._add_event(event, newest=False)
        session.bus.event.connect(self._add_event)
        session.bus.run_reset.connect(self.event_list.clear)

    def _add_event(self, event: Event, newest: bool = True) -> None:
        text = format_event(event)
        if newest:
            self.event_list.insertItem(0, text)
        else:
            self.event_list.addItem(text)

    def _on_log_clicked(self, *_args) -> None:
        self.log_requested.emit()


class AnalysisPage(QWidget):
    """The Dataset Analysis default view, with the simulation-run Validation beside it.

    A dataset analysis scores the twin on imported measurements (no plant needed); the
    Validation view scores it against runs it generates itself. One of the two is in front,
    chosen by the two buttons on the right of the page title.
    """

    DATASET_TITLE = "Dataset Analysis"
    DATASET_SUB = "Import a CSV or Excel file of measurements to score the Digital Twin — works without the ESP32"
    SIMULATION_TITLE = "Validation Analysis"
    SIMULATION_SUB = "Test the Digital Twin against known answers: one healthy day and one day for each fault"

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.validation = ValidationView(session.config, palette=session.theme.palette)
        self.datasets = DatasetAnalysisView(session.config, session.datasets, palette=session.theme.palette)
        self.datasets.replay_requested.connect(session.replay_dataset)
        session.config_changed.connect(self.validation.set_config)
        session.config_changed.connect(self.datasets.set_config)

        self.dataset_button = QPushButton("DATASET")
        self.dataset_button.setProperty("seg", "true")
        self.dataset_button.setCheckable(True)
        self.dataset_button.setChecked(True)
        self.dataset_button.clicked.connect(self._show_datasets)
        self.simulation_button = QPushButton("SIMULATION")
        self.simulation_button.setProperty("seg", "true")
        self.simulation_button.setCheckable(True)
        self.simulation_button.clicked.connect(self._show_simulation)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.dataset_button)
        group.addButton(self.simulation_button)

        self.title_label = role_label(self.DATASET_TITLE, "pageTitle")
        self.sub_label = role_label(self.DATASET_SUB, "pageSub")
        row = QHBoxLayout()
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addWidget(self.title_label)
        column.addWidget(self.sub_label)
        row.addLayout(column)
        row.addStretch(1)
        row.addWidget(self.dataset_button, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.simulation_button, 0, Qt.AlignmentFlag.AlignTop)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.datasets)
        self.stack.addWidget(self.validation)

        layout = page_layout(self)
        layout.addLayout(row)
        layout.addWidget(self.stack, 1)

        session.theme.changed.connect(self._apply_palette)

    def shutdown(self) -> None:
        self.validation.shutdown()  # a running validation ends before the window closes
        self.datasets.shutdown()  # so does a running dataset analysis

    def _show_datasets(self, *_args) -> None:
        self.stack.setCurrentWidget(self.datasets)
        self.title_label.setText(self.DATASET_TITLE)
        self.sub_label.setText(self.DATASET_SUB)

    def _show_simulation(self, *_args) -> None:
        self.stack.setCurrentWidget(self.validation)
        self.title_label.setText(self.SIMULATION_TITLE)
        self.sub_label.setText(self.SIMULATION_SUB)

    def _apply_palette(self, palette: Palette) -> None:
        self.validation.strip.set_palette(palette)
        self.datasets.apply_palette(palette)


class ModelPage(QWidget):
    """The Single Diode Model the twin computes: circuit, equations, parameters and live curves."""

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.model_view = ModelView(session.playback, session.bus, theme=session.theme)
        layout = page_layout(self)
        layout.addLayout(page_header("SDM Model", "What the twin is computing for the measured irradiance and temperature"))
        layout.addWidget(self.model_view, 1)


class SettingsPage(QWidget):
    """The setup of the next run: profile, site, module and limits. Applying it starts a new run."""

    apply_requested = pyqtSignal(object)  # RunConfig

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self.setup_view = SetupView(session.config, session.theme)
        self.setup_view.apply_requested.connect(self.apply_requested)
        session.config_changed.connect(self.setup_view.follow_config)
        layout = page_layout(self)
        layout.addLayout(page_header("Settings", "Profile, site, module and limits for the next run"))
        layout.addWidget(self.setup_view, 1)

    def shutdown(self) -> None:
        self.setup_view.shutdown()  # a running fetch ends before the window closes
