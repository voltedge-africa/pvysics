"""The HMI Process view: what the plant is doing, what the twin expects, and how far apart they are.

Top to bottom: one toolbar (run controls, fault injection, the state), a strip of figures drawn in QML
(plant, twin, deviation with its gauge), the power trend, and the alarm list. Nothing is boxed: the figures
and the chart sit on the window. Colours come from the palette and the stylesheet, and sizes from layouts and
font metrics, so the view scales with font, DPI and theme.
"""

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from pvysics.gui.data_bus import DataBus
from pvysics.gui.metric_strip import GAUGE_SCALE_FACTOR, Group, MetricStrip, Tile
from pvysics.gui.palette import LIGHT, STATE_COLOURS, Palette
from pvysics.gui.playback import PlaybackController
from pvysics.gui.run_toolbar import PLACEHOLDER, RunToolbar
from pvysics.gui.trend import PowerTrend
from pvysics.gui.ui_helpers import pane, role_label
from pvysics.history import RunHistory
from pvysics.run import POWER_FLOOR_W, Sample, State, Thresholds

NIGHT_SENTENCE = "Too little light to compare."
NIGHT_DETAIL = "The twin and the plant both read close to zero, so the state stays Normal."
DEVIATION_KEY = "deviation"
# The HMI shows the deviation and what the twin predicts. The plant's measured readings belong to the Dashboard.
STRIP_GROUPS = [
    Group("Deviation", [Tile(DEVIATION_KEY, "", "hero")], columns=1, weight=4),
    Group("Twin", [Tile("P_pred", "Predicted power", "large")], columns=1, weight=1),
]

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
        self.toolbar = RunToolbar(controller, bus)
        # The toolbar's controls are the view's own to callers: the tests and the HMI reach them here.
        self.start_button = self.toolbar.start_button
        self.pause_button = self.toolbar.pause_button
        self.reset_button = self.toolbar.reset_button
        self.speed_box = self.toolbar.speed_box
        self.time_label = self.toolbar.time_label
        self.fault_buttons = self.toolbar.fault_buttons
        self.clear_faults_button = self.toolbar.clear_faults_button
        layout.addWidget(self.toolbar)
        layout.addWidget(self.strip)
        layout.addWidget(pane(self.trend), 1)

        bus.sample.connect(self._show_sample)
        bus.run_reset.connect(self._show_start)
        if theme is not None:
            theme.changed.connect(self._apply_palette)
        if history is not None:
            for sample in history.samples_from(0):
                self.trend.add_sample(sample)
            self.trend.flush()

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
        self.trend.add_sample(sample)

    def _show_start(self) -> None:
        self.strip.setToolTip("")
        self.strip.clear()
        thresholds = self._controller.config.thresholds
        self.strip.set_limits(thresholds.warning_pct, thresholds.abnormal_pct)
        self.trend.clear()
