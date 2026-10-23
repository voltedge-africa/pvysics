"""The HMI Process view: plant readings, twin prediction, deviation gauge, state banner,
fault injection, alarms and run controls.

Layout follows the HMI wireframe: banner on top, plant panel left, twin panel middle,
deviation panel right, fault injection and alarms below, run controls at the bottom.
Sizes come from layouts and font metrics, so the view scales with the platform font and DPI.
"""

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pvysics.alarms import Alarm, AlarmLog
from pvysics.faults import FaultKind, default_fault
from pvysics.gui.data_bus import DataBus
from pvysics.gui.playback import SPEEDS, PlaybackController
from pvysics.run import Sample, State, Thresholds

PLACEHOLDER = "-"
IDLE_TEXT = "Ready"
IDLE_COLOUR = "#616161"
STATE_COLOURS = {State.NORMAL: "#2e7d32", State.WARNING: "#f2a900", State.ABNORMAL: "#c62828"}
STATE_TEXT_COLOURS = {State.NORMAL: "#ffffff", State.WARNING: "#000000", State.ABNORMAL: "#ffffff"}
GAUGE_SCALE_FACTOR = 1.5  # the gauge runs from 0 to this multiple of the abnormal limit

PLANT_READINGS = [
    ("G", "Irradiance G"),
    ("T", "Module temp T"),
    ("V", "Voltage V"),
    ("I", "Current I"),
    ("P", "Power P measured"),
]
TWIN_READINGS = [("P_pred", "Power P predicted")]
FAULT_BUTTON_LABELS = {
    FaultKind.PARTIAL_SHADING: "Partial shading",
    FaultKind.SOILING: "Soiling",
    FaultKind.SERIES_RESISTANCE_RISE: "Rs increase",
    FaultKind.DIODE_FAILURE: "Diode failure",
    FaultKind.SENSOR_DRIFT: "Sensor drift",
}
MUTED_TEXT_COLOUR = "#757575"


def format_number(value: float, decimals: int, signed: bool = False) -> str:
    """Fixed-point text. A value that rounds to zero is shown as 0, never as negative zero."""
    if round(value, decimals) == 0:
        value = 0.0
    return f"{value:+.{decimals}f}" if signed else f"{value:.{decimals}f}"


def format_readings(sample: Sample) -> dict[str, str]:
    """The display text for every reading in a Sample, keyed as in PLANT_READINGS and TWIN_READINGS."""
    return {
        "G": f"{format_number(sample.measured_irradiance, 0)} W/m²",
        "T": f"{format_number(sample.measured_temperature, 1)} °C",
        "V": f"{format_number(sample.measured_voltage, 1)} V",
        "I": f"{format_number(sample.measured_current, 1)} A",
        "P": f"{format_number(sample.power_measured, 1)} W",
        "P_pred": f"{format_number(sample.power_predicted, 1)} W",
    }


def _tinted(colour: str, alpha: float) -> QColor:
    tint = QColor(colour)
    tint.setAlphaF(alpha)
    return tint


class StateBanner(QLabel):
    """Full-width banner: the State in green, amber or red, or grey before a run starts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.font()
        font.setBold(True)
        self.setFont(font)
        self._colour = IDLE_COLOUR
        self.show_state(None)

    def colour(self) -> str:
        return self._colour

    def show_state(self, state: State | None) -> None:
        if state is None:
            text, colour, text_colour = IDLE_TEXT, IDLE_COLOUR, "#ffffff"
        else:
            text, colour, text_colour = state.value, STATE_COLOURS[state], STATE_TEXT_COLOURS[state]
        self._colour = colour
        self.setText(text)
        self.setStyleSheet(f"background-color: {colour}; color: {text_colour};")


class ReadingsPanel(QGroupBox):
    """A titled group of readings, each a caption and a value."""

    def __init__(self, title: str, readings: list[tuple[str, str]], parent: QWidget | None = None):
        super().__init__(title, parent)
        grid = QGridLayout(self)
        self._values: dict[str, QLabel] = {}
        for row, (key, caption) in enumerate(readings):
            value = QLabel(PLACEHOLDER)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(QLabel(caption), row, 0)
            grid.addWidget(value, row, 1)
            self._values[key] = value
        grid.setRowStretch(len(readings), 1)

    def value(self, key: str) -> str:
        return self._values[key].text()

    def set_values(self, values: dict[str, str]) -> None:
        for key, label in self._values.items():
            label.setText(values[key])

    def clear(self) -> None:
        for label in self._values.values():
            label.setText(PLACEHOLDER)


class DeviationGauge(QWidget):
    """Absolute power deviation on a bar, with the warning and abnormal bands marked on the track."""

    def __init__(self, thresholds: Thresholds, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thresholds = thresholds
        self._reading_pct = 0.0
        self._state: State | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(self.fontMetrics().height() * 4)

    @property
    def reading_pct(self) -> float:
        return self._reading_pct

    @property
    def state(self) -> State | None:
        return self._state

    @property
    def scale_pct(self) -> float:
        return GAUGE_SCALE_FACTOR * self._thresholds.abnormal_pct

    def show_deviation(self, deviation_pct: float, state: State) -> None:
        self._reading_pct = abs(deviation_pct)
        self._state = state
        self.update()

    def clear(self) -> None:
        self._reading_pct = 0.0
        self._state = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        metrics = self.fontMetrics()
        margin = metrics.height() / 2
        track = QRectF(
            margin,
            margin,
            self.width() - 2 * margin,
            self.height() - 2 * margin - metrics.height(),
        )

        def x_at(pct: float) -> float:
            return track.left() + track.width() * min(pct, self.scale_pct) / self.scale_pct

        warning, abnormal = self._thresholds.warning_pct, self._thresholds.abnormal_pct
        bands = [
            (0.0, warning, State.NORMAL),
            (warning, abnormal, State.WARNING),
            (abnormal, self.scale_pct, State.ABNORMAL),
        ]
        for start, end, state in bands:
            span = QRectF(x_at(start), track.top(), x_at(end) - x_at(start), track.height())
            painter.fillRect(span, _tinted(STATE_COLOURS[state], 0.3))
        if self._state is not None:
            bar = QRectF(
                track.left(),
                track.top() + track.height() * 0.3,
                x_at(self._reading_pct) - track.left(),
                track.height() * 0.4,
            )
            painter.fillRect(bar, QColor(STATE_COLOURS[self._state]))

        painter.setPen(QPen(self.palette().text().color()))
        for limit in (warning, abnormal):
            x = x_at(limit)
            painter.drawLine(QPointF(x, track.top()), QPointF(x, track.bottom()))
            half_width = metrics.horizontalAdvance("10 %")
            label = QRectF(x - half_width, track.bottom(), 2 * half_width, metrics.height())
            align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            painter.drawText(label, align, f"{limit:g} %")
        painter.end()


def format_alarm(alarm: Alarm) -> str:
    stamp = np.datetime_as_string(alarm.timestamp, unit="s").split("T")[1]
    text = (
        f"{stamp}  {alarm.severity.value.upper()}  Deviation {abs(alarm.deviation_pct):.1f} %"
        f"  Probable cause: {alarm.cause}"
    )
    return f"{text}  (acknowledged)" if alarm.acknowledged else text


class AlarmPanel(QGroupBox):
    """The alarm list, newest first. Unacknowledged alarms are bold and tinted by severity."""

    def __init__(self, bus: DataBus, parent: QWidget | None = None) -> None:
        super().__init__("Alarms", parent)
        self.log = AlarmLog()
        self.summary_label = QLabel()
        self.list_widget = QListWidget()
        self.acknowledge_button = QPushButton("Acknowledge")
        self.acknowledge_button.setEnabled(False)

        header = QHBoxLayout()
        header.addWidget(self.summary_label)
        header.addStretch(1)
        header.addWidget(self.acknowledge_button)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.list_widget)

        self.acknowledge_button.clicked.connect(self._acknowledge_selected)
        self.list_widget.itemSelectionChanged.connect(self._refresh_buttons)
        bus.sample.connect(self._on_sample)
        bus.run_reset.connect(self._on_reset)
        self._refresh()

    def _on_sample(self, sample: Sample) -> None:
        if self.log.record(sample) is not None:
            self._refresh()

    def _on_reset(self) -> None:
        self.log.clear()
        self._refresh()

    def _acknowledge_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is not None:
            self.log.acknowledge(item.data(Qt.ItemDataRole.UserRole))
            self._refresh()

    def _refresh(self) -> None:
        current = self.list_widget.currentItem()
        selected = None if current is None else current.data(Qt.ItemDataRole.UserRole)
        self.list_widget.blockSignals(True)  # rebuild quietly, then update the buttons once
        self.list_widget.clear()
        for index, alarm in reversed(list(enumerate(self.log.alarms))):
            item = QListWidgetItem(format_alarm(alarm))
            item.setData(Qt.ItemDataRole.UserRole, index)
            if alarm.acknowledged:
                item.setForeground(QBrush(QColor(MUTED_TEXT_COLOUR)))
            else:
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
                item.setBackground(QBrush(_tinted(STATE_COLOURS[alarm.severity], 0.25)))
            self.list_widget.addItem(item)
            if index == selected:
                self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)
        if selected is None:
            self._select_newest_unacknowledged()
        unacknowledged = self.log.unacknowledged_count
        self.summary_label.setText(f"{unacknowledged} new" if unacknowledged else "No new alarms")
        self._refresh_buttons()

    def _select_newest_unacknowledged(self) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if not self._alarm_of(item).acknowledged:
                self.list_widget.setCurrentItem(item)
                return

    def _refresh_buttons(self) -> None:
        item = self.list_widget.currentItem()
        selected = item is not None and not self._alarm_of(item).acknowledged
        self.acknowledge_button.setEnabled(selected)

    def _alarm_of(self, item: QListWidgetItem) -> Alarm:
        return self.log.alarms[item.data(Qt.ItemDataRole.UserRole)]


class ProcessView(QWidget):
    """The Process screen. Subscribes to the DataBus and drives the PlaybackController."""

    def __init__(self, controller: PlaybackController, bus: DataBus, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        self.banner = StateBanner()
        self.plant = ReadingsPanel("Plant (measured)", PLANT_READINGS)
        self.twin = ReadingsPanel("Digital twin (predicted)", TWIN_READINGS)
        self.gauge = DeviationGauge(controller.config.thresholds)
        self.deviation_label = QLabel(PLACEHOLDER)
        self.deviation_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        deviation_panel = QGroupBox("Power deviation")
        deviation_layout = QVBoxLayout(deviation_panel)
        deviation_layout.addWidget(self.deviation_label)
        deviation_layout.addWidget(self.gauge)
        deviation_layout.addStretch(1)

        panels = QHBoxLayout()
        for panel in (self.plant, self.twin, deviation_panel):
            panels.addWidget(panel, 1)

        self.alarm_panel = AlarmPanel(bus)
        lower = QHBoxLayout()
        lower.addWidget(self._build_fault_panel())
        lower.addWidget(self.alarm_panel, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.banner)
        layout.addLayout(panels, 1)
        layout.addLayout(lower)
        layout.addLayout(self._build_controls())

        bus.sample.connect(self._show_sample)
        bus.run_reset.connect(self._show_start)
        controller.running_changed.connect(lambda _running: self._refresh_controls())
        self._refresh_controls()

    def _build_fault_panel(self) -> QGroupBox:
        panel = QGroupBox("Fault injection")
        layout = QVBoxLayout(panel)
        self.fault_buttons: dict[FaultKind, QPushButton] = {}
        for kind, label in FAULT_BUTTON_LABELS.items():
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, kind=kind: self._inject(kind))
            layout.addWidget(button)
            self.fault_buttons[kind] = button
        self.clear_faults_button = QPushButton("Clear all")
        self.clear_faults_button.clicked.connect(lambda: self._controller.clear_faults())
        layout.addWidget(self.clear_faults_button)
        layout.addStretch(1)
        return panel

    def _inject(self, kind: FaultKind) -> None:
        self._controller.inject(default_fault(kind))

    def _build_controls(self) -> QHBoxLayout:
        self.start_button = QPushButton("Start")
        self.pause_button = QPushButton("Pause")
        self.reset_button = QPushButton("Reset")
        self.speed_box = QComboBox()
        for speed in SPEEDS:
            self.speed_box.addItem(f"{speed:g}x", speed)
        self.time_label = QLabel(PLACEHOLDER)

        self.start_button.clicked.connect(lambda: self._controller.start())
        self.pause_button.clicked.connect(lambda: self._controller.pause())
        self.reset_button.clicked.connect(lambda: self._controller.reset())
        self.speed_box.currentIndexChanged.connect(self._on_speed_chosen)

        row = QHBoxLayout()
        for button in (self.start_button, self.pause_button, self.reset_button):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(QLabel("Speed"))
        row.addWidget(self.speed_box)
        row.addWidget(self.time_label)
        return row

    def _on_speed_chosen(self, index: int) -> None:
        self._controller.set_speed(self.speed_box.itemData(index))

    def _refresh_controls(self) -> None:
        running = self._controller.is_running
        self.start_button.setEnabled(not running and not self._controller.is_finished)
        self.pause_button.setEnabled(running)

    def _show_sample(self, sample: Sample) -> None:
        readings = format_readings(sample)
        self.plant.set_values(readings)
        self.twin.set_values(readings)
        self.banner.show_state(sample.state)
        self.gauge.show_deviation(sample.deviation_pct, sample.state)
        self.deviation_label.setText(f"{format_number(sample.deviation_pct, 1, signed=True)} %")
        self.time_label.setText(np.datetime_as_string(sample.timestamp, unit="m").replace("T", " "))

    def _show_start(self) -> None:
        self.banner.show_state(None)
        self.plant.clear()
        self.twin.clear()
        self.gauge.clear()
        self.deviation_label.setText(PLACEHOLDER)
        self.time_label.setText(PLACEHOLDER)
