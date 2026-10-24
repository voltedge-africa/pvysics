"""The HMI Process view: what the plant is doing, what the twin expects, and how far apart they are.

Top to bottom: one toolbar (run controls, fault injection, the state), a strip of figures drawn in QML
(plant, twin, deviation with its gauge), the power trend, and the alarm list. Nothing is boxed: the figures
and the chart sit on the window. Colours come from the palette and the stylesheet, and sizes from layouts and
font metrics, so the view scales with font, DPI and theme.
"""

import logging

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
        QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
        QVBoxLayout,
    QWidget,
)

from pvysics.faults import FaultKind, default_fault
from pvysics.gui.data_bus import DataBus
from pvysics.gui.metric_strip import GAUGE_SCALE_FACTOR, Group, MetricStrip, Tile
from pvysics.gui.palette import LIGHT, STATE_COLOURS, Palette
from pvysics.gui.playback import SPEEDS, PlaybackController
from pvysics.gui.trend import PowerTrend
from pvysics.gui.ui_helpers import pane, role_label, set_property, vertical_separator
from pvysics.history import RunHistory
from pvysics.run import POWER_FLOOR_W, Sample, State, Thresholds

PLACEHOLDER = "-"

NIGHT_SENTENCE = "Too little light to compare."
NIGHT_DETAIL = "The twin and the plant both read close to zero, so the state stays Normal."
DEVIATION_KEY = "deviation"
# The HMI shows the deviation and what the twin predicts. The plant's measured readings belong to the Dashboard.
STRIP_GROUPS = [
    Group("Deviation", [Tile(DEVIATION_KEY, "", "hero")], columns=1, weight=4),
    Group("Twin", [Tile("P_pred", "Predicted power", "large")], columns=1, weight=1),
]
FAULT_BUTTON_LABELS = {
    FaultKind.PARTIAL_SHADING: "Partial shading",
    FaultKind.SOILING: "Soiling",
    FaultKind.SERIES_RESISTANCE_RISE: "Rs increase",
    FaultKind.DIODE_FAILURE: "Diode failure",
    FaultKind.SENSOR_DRIFT: "Sensor drift",
}
FAULT_TOOLTIPS = {
    FaultKind.PARTIAL_SHADING: "Part of the module is shaded: less photocurrent, so less power.",
    FaultKind.SOILING: "Dust on the glass: less light reaches the cells.",
    FaultKind.SERIES_RESISTANCE_RISE: "A degraded connection: more series resistance, so more loss.",
    FaultKind.DIODE_FAILURE: "A bypass diode has failed: a group of cells drops out.",
    FaultKind.SENSOR_DRIFT: "The irradiance sensor reads high: the twin predicts wrongly, the plant is fine.",
}


def format_number(value: float, decimals: int, signed: bool = False) -> str:
    """Fixed-point text. A value that rounds to zero is shown as 0, never as negative zero."""
    if round(value, decimals) == 0:
        value = 0.0
    return f"{value:+.{decimals}f}" if signed else f"{value:.{decimals}f}"


def format_readings(sample: Sample) -> dict[str, str]:
    """The display text for every reading in a Sample, keyed as in STRIP_GROUPS."""
    return {
        "G": f"{format_number(sample.measured_irradiance, 0)} W/m²",
        "T": f"{format_number(sample.measured_temperature, 1)} °C",
        "V": f"{format_number(sample.measured_voltage, 1)} V",
        "I": f"{format_number(sample.measured_current, 1)} A",
        "P": f"{format_number(sample.power_measured, 1)} W",
        "P_pred": f"{format_number(sample.power_predicted, 1)} W",
    }


class ReadingsPanel(QGroupBox):
    """A titled block of readings. The first reading is the headline figure, the rest are listed below it."""

    def __init__(
        self,
        title: str,
        readings: list[tuple[str, str]],
        note: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(title, parent)
        self._values: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        (head_key, head_caption), rest = readings[0], readings[1:]
        head_value = role_label(PLACEHOLDER, "hero")
        self._values[head_key] = head_value
        layout.addWidget(head_value)
        layout.addWidget(role_label(head_caption, "caption"))
        if note:
            self.setToolTip(note)  # the explanation is a tooltip, so the card stays short
        if rest:
            grid = QGridLayout()  # two readings per row: caption, value, caption, value
            for index, (key, caption) in enumerate(rest):
                row, column = divmod(index, 2)
                value = QLabel(PLACEHOLDER)
                value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(role_label(caption, "muted"), row, 2 * column)
                grid.addWidget(value, row, 2 * column + 1)
                grid.setColumnStretch(2 * column + 1, 1)
                self._values[key] = value
            layout.addLayout(grid)
        layout.addStretch(1)

    def value(self, key: str) -> str:
        return self._values[key].text()

    def set_values(self, values: dict[str, str]) -> None:
        for key, label in self._values.items():
            label.setText(values[key])

    def clear(self) -> None:
        for label in self._values.values():
            label.setText(PLACEHOLDER)


def describe_state(sample: Sample, thresholds: Thresholds) -> tuple[str, str]:
    """A sentence and a detail line that say what the state means, in words an operator can read at a glance."""
    if sample.power_predicted < POWER_FLOOR_W:
        return NIGHT_SENTENCE, NIGHT_DETAIL
    deviation = sample.deviation_pct
    side = "above" if deviation > 0 else "below"
    sentence = f"{abs(deviation):.1f} % {side} the prediction."
    detail = {
        State.NORMAL: f"Within the {thresholds.warning_pct:g} % warning limit.",
        State.WARNING: f"Past the {thresholds.warning_pct:g} % warning limit.",
        State.ABNORMAL: f"Past the {thresholds.abnormal_pct:g} % abnormal limit.",
    }[sample.state]
    return sentence, detail


class ProcessView(QWidget):
    """The Process screen. Subscribes to the DataBus and drives the PlaybackController.

    theme gives the trend and the strip their colours (the light palette if none); history, if given, fills
    the trend with the run so far when the window is first opened in the middle of a run. The alarm panel is
    a member of the view; the HMI window may dock it elsewhere.
    """

    def __init__(
        self,
        controller: PlaybackController,
        bus: DataBus,
        parent: QWidget | None = None,
        theme=None,
        history: RunHistory | None = None,
    ):
        super().__init__(parent)
        self._controller = controller
        palette = LIGHT if theme is None else theme.palette
        self.strip = MetricStrip(STRIP_GROUPS, palette, gauge_key=DEVIATION_KEY)
        self.strip.set_limits(controller.config.thresholds.warning_pct, controller.config.thresholds.abnormal_pct)
        self.trend = PowerTrend(palette)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self.strip)
        layout.addWidget(pane(self.trend), 1)

        bus.sample.connect(self._show_sample)
        bus.run_reset.connect(self._show_start)
        controller.running_changed.connect(self._on_running_changed)
        if theme is not None:
            theme.changed.connect(self._apply_palette)
        if history is not None:
            for sample in history.samples_from(0):
                self.trend.add_sample(sample)
            self.trend.flush()
        self._refresh_controls()

    def _build_toolbar(self) -> QWidget:
        """One row, as an editor has: run controls, speed and clock, fault injection, then the state.

        The left is what the operator does, the right is what the plant is doing, so the controls and the
        answer to "is it OK?" share a line and the faults are always one click away.
        """
        self.start_button = QPushButton("Start")
        set_property(self.start_button, "variant", "primary")
        self.pause_button = QPushButton("Pause")
        self.reset_button = QPushButton("Reset")
        self.reset_button.setToolTip("Back to the start. Faults and alarms are cleared.")
        self.start_button.clicked.connect(self._on_start_clicked)
        self.pause_button.clicked.connect(self._on_pause_clicked)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.speed_box = QComboBox()
        for speed in SPEEDS:
            self.speed_box.addItem(f"{speed:g}x", speed)
        self.speed_box.setToolTip("Playback speed")
        self.speed_box.currentIndexChanged.connect(self._on_speed_chosen)
        self.time_label = role_label(PLACEHOLDER, "muted")

        self.fault_buttons: dict[FaultKind, QPushButton] = {}
        for kind, label in FAULT_BUTTON_LABELS.items():
            button = QPushButton(label)
            button.setToolTip(FAULT_TOOLTIPS[kind])
            button.setProperty("kind", kind.name)
            button.clicked.connect(self._on_fault_clicked)
            self.fault_buttons[kind] = button
        self.clear_faults_button = QPushButton("Clear all")
        self.clear_faults_button.setToolTip("Remove every injected fault.")
        self.clear_faults_button.clicked.connect(self._on_clear_clicked)

        for button in (self.pause_button, self.reset_button, self.clear_faults_button, *self.fault_buttons.values()):
            set_property(button, "variant", "tool")  # flat until hovered, like an editor's toolbar
        for button in (self.start_button, self.pause_button, self.reset_button, self.clear_faults_button,
                       *self.fault_buttons.values()):
            button.setProperty("compact", "true")

        toolbar = QWidget()
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        for widget in (self.start_button, self.pause_button, self.reset_button):
            row.addWidget(widget)
        row.addWidget(vertical_separator())
        row.addWidget(self.speed_box)
        row.addWidget(self.time_label)
        row.addStretch(1)
        row.addWidget(role_label("Inject a fault", "muted"))
        for button in self.fault_buttons.values():
            row.addWidget(button)
        row.addWidget(self.clear_faults_button)
        return toolbar

    def _on_fault_clicked(self, *_args) -> None:
        kind = FaultKind[self.sender().property("kind")]
        self._controller.inject(default_fault(kind))

    def _on_clear_clicked(self, *_args) -> None:
        self._controller.clear_faults()

    def _on_start_clicked(self, *_args) -> None:
        self._controller.start()

    def _on_pause_clicked(self, *_args) -> None:
        self._controller.pause()

    def _on_reset_clicked(self, *_args) -> None:
        self._controller.reset()

    def _on_speed_chosen(self, index: int) -> None:
        self._controller.set_speed(self.speed_box.itemData(index))

    def _on_running_changed(self, _running: bool) -> None:
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        running = self._controller.is_running
        self.start_button.setEnabled(not running and not self._controller.is_finished)
        self.pause_button.setEnabled(running)

    def _apply_palette(self, palette: Palette) -> None:
        self.trend.apply_palette(palette)
        self.strip.set_palette(palette)

    def _show_sample(self, sample: Sample) -> None:
        readings = format_readings(sample)
        readings[DEVIATION_KEY] = f"{format_number(sample.deviation_pct, 1, signed=True)} %"
        self.strip.set_values(readings)
        sentence, detail = describe_state(sample, self._controller.config.thresholds)
        self.strip.set_status(sample.state.value, sample.state, sentence)
        self.strip.setToolTip(detail)
        thresholds = self._controller.config.thresholds
        self.strip.set_gauge(sample.deviation_pct, sample.state, thresholds.warning_pct, thresholds.abnormal_pct)
        self.time_label.setText(np.datetime_as_string(sample.timestamp, unit="m").replace("T", " "))
        for kind, button in self.fault_buttons.items():
            set_property(button, "variant", "active" if kind in sample.active_faults else "tool")
        self.trend.add_sample(sample)

    def _show_start(self) -> None:
        self.strip.setToolTip("")
        self.strip.clear()
        thresholds = self._controller.config.thresholds
        self.strip.set_limits(thresholds.warning_pct, thresholds.abnormal_pct)
        self.time_label.setText(PLACEHOLDER)
        for button in self.fault_buttons.values():
            set_property(button, "variant", "tool")
        self.trend.clear()
