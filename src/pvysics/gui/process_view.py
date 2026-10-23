"""The HMI Process view: what the plant is doing, what the twin expects, and how far apart they are.

Top to bottom: a status strip (the state, a sentence that says what it means, and the run controls),
three headline cards (plant, twin, deviation), a live power trend, then fault injection and alarms.
The strip puts the answer to "is it OK?" and the controls where the eye starts. Sizes come from layouts
and font metrics, and colours from the palette and stylesheet, so the view scales with font, DPI and theme.
"""

import logging

import numpy as np
from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pvysics.alarms import Alarm, AlarmLog
from pvysics.faults import FaultKind, default_fault
from pvysics.gui.data_bus import DataBus
from pvysics.gui.metric_tile import MetricSet, MetricTile, section_label
from pvysics.gui.palette import LIGHT, STATE_COLOURS, STATE_TEXT_COLOURS, Palette
from pvysics.gui.playback import SPEEDS, PlaybackController
from pvysics.gui.trend import PowerTrend
from pvysics.gui.ui_helpers import ElidedLabel, role_label, set_property, vertical_separator
from pvysics.history import RunHistory
from pvysics.run import POWER_FLOOR_W, Sample, State, Thresholds

PLACEHOLDER = "-"
IDLE_TEXT = "Ready"
IDLE_COLOUR = "#616161"
DEVIATION_COLUMNS = 3  # the deviation tile is this many tiles wide: its gauge needs the room
ALARMS_MAX_PX = 120  # the alarm list stays compact so the trend gets the room
GAUGE_SCALE_FACTOR = 1.5  # the gauge runs from 0 to this multiple of the abnormal limit

IDLE_SENTENCE = ""
IDLE_DETAIL = "The twin predicts power from the measured irradiance and temperature, then compares."
NIGHT_SENTENCE = "Too little light to compare."
NIGHT_DETAIL = "The twin and the plant both read close to zero, so the state stays Normal."
# (key, caption); the first reading of a panel is its headline figure.
PLANT_READINGS = [
    ("G", "Irradiance G"),
    ("T", "Module temp T"),
    ("V", "Voltage V"),
    ("I", "Current I"),
    ("P", "Power P measured"),
]
TWIN_READINGS = [("P_pred", "Power P predicted")]
TWIN_NOTE = "Single Diode Model with the datasheet parameters, evaluated at the measured G and T."
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
    """The State as a coloured pill: green, amber or red, or grey before a run starts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance("Abnormal") * 3 // 2)
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
        self.setVisible(state is not None)  # nothing to say before a run starts
        self.setStyleSheet(
            f"background-color: {colour}; color: {text_colour}; border-radius: 6px;"
            " padding: 3px 12px; font-weight: 700;"
        )


class ReadingsPanel(QGroupBox):
    """A titled card of readings. The first reading is the headline figure, the rest are listed below it."""

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

    def set_thresholds(self, thresholds: Thresholds) -> None:
        """Redraw the bands and the scale for new limits."""
        self._thresholds = thresholds
        self.update()

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


log = logging.getLogger(__name__)


def log_alarm(alarm: Alarm) -> None:
    """A Warning alarm logs a WARNING line and an Abnormal alarm an ERROR line."""
    level = logging.ERROR if alarm.severity is State.ABNORMAL else logging.WARNING
    log.log(
        level,
        "Alarm %s: deviation %.1f %%, probable cause: %s",
        alarm.severity.value,
        abs(alarm.deviation_pct),
        alarm.cause,
    )


class AlarmPanel(QGroupBox):
    """The alarm list, newest first. Unacknowledged alarms are bold and tinted by severity."""

    def __init__(self, bus: DataBus, parent: QWidget | None = None) -> None:
        super().__init__("Alarms", parent)
        self.log = AlarmLog()
        self.summary_label = QLabel()
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(self.fontMetrics().height() * 3)  # three rows; it scrolls when more
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

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and hasattr(self, "log"):
            self._refresh()  # the muted colour of acknowledged alarms follows the palette

    def _on_sample(self, sample: Sample) -> None:
        alarm = self.log.record(sample)
        if alarm is not None:
            log_alarm(alarm)
            self._refresh()

    def _on_reset(self) -> None:
        self.log.clear()
        self._refresh()

    def _acknowledge_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is not None:
            index = item.data(Qt.ItemDataRole.UserRole)
            self.log.acknowledge(index)
            alarm = self.log.alarms[index]
            log.info("Alarm acknowledged: %s, probable cause: %s", alarm.severity.value, alarm.cause)
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
                item.setForeground(QBrush(self.palette().color(QPalette.ColorRole.PlaceholderText)))
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


def describe_state(sample: Sample, thresholds: Thresholds) -> tuple[str, str]:
    """A sentence and a detail line that say what the state means, in words an operator can read at a glance."""
    if sample.power_predicted < POWER_FLOOR_W:
        return NIGHT_SENTENCE, NIGHT_DETAIL
    deviation = sample.deviation_pct
    side = "above" if deviation > 0 else "below"
    sentence = f"Plant output is {abs(deviation):.1f} % {side} the twin's prediction."
    detail = {
        State.NORMAL: f"Within the warning limit of {thresholds.warning_pct:g} %: the plant behaves as modelled.",
        State.WARNING: f"Past the warning limit of {thresholds.warning_pct:g} %: worth a look.",
        State.ABNORMAL: f"Past the abnormal limit of {thresholds.abnormal_pct:g} %: the plant is not behaving as modelled.",
    }[sample.state]
    return sentence, detail


class ProcessView(QScrollArea):
    """The Process screen. Subscribes to the DataBus and drives the PlaybackController.

    It fills the window and scrolls only when the window is too small to show it, so it never forces the
    window taller than a laptop screen.

    theme gives the trend its colours (the light palette if none); history, if given, fills the trend
    with the run so far when the window is first opened in the middle of a run.
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
        self.banner = StateBanner()
        self.summary_label = ElidedLabel(IDLE_SENTENCE)
        self.summary_label.setProperty("role", "strong")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.summary_label.setToolTip(IDLE_DETAIL)  # the explanation is a tooltip, so the toolbar stays one row
        self.plant = MetricSet({key: MetricTile(caption) for key, caption in PLANT_READINGS})
        self.twin = MetricSet({key: MetricTile(caption) for key, caption in TWIN_READINGS})
        self.twin.tiles["P_pred"].setToolTip(TWIN_NOTE)
        self.gauge = DeviationGauge(controller.config.thresholds)
        self.deviation_tile = MetricTile("Deviation", side=self.gauge)
        self.trend = PowerTrend(palette)
        self.alarm_panel = AlarmPanel(bus)

        cards = self._build_measurement_row()

        trend_panel = QGroupBox("Power over the run")
        QVBoxLayout(trend_panel).addWidget(self.trend)

        self.alarm_panel.setMaximumHeight(ALARMS_MAX_PX)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.addWidget(self._build_toolbar())
        layout.addLayout(cards)
        layout.addWidget(trend_panel, 1)
        layout.addWidget(self.alarm_panel)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidget(content)

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

    def _build_measurement_row(self) -> QGridLayout:
        """Seven tiles in one row under three small headings: the plant, the twin, and how far apart they are."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        plant_tiles = list(self.plant.tiles.values())
        for column, tile in enumerate(plant_tiles):
            grid.addWidget(tile, 1, column)
        twin_column = len(plant_tiles)
        grid.addWidget(self.twin.tiles["P_pred"], 1, twin_column)
        deviation_column = twin_column + 1
        grid.addWidget(self.deviation_tile, 1, deviation_column, 1, DEVIATION_COLUMNS)
        grid.addWidget(section_label("Plant, measured"), 0, 0, 1, twin_column)
        grid.addWidget(section_label("Twin"), 0, twin_column)
        grid.addWidget(section_label("Comparison"), 0, deviation_column, 1, DEVIATION_COLUMNS)
        for column in range(deviation_column + DEVIATION_COLUMNS):
            grid.setColumnStretch(column, 1)
        return grid

    def _build_toolbar(self) -> QFrame:
        """One row, as an editor has: run controls, speed and clock, fault injection, then the state.

        The left is what the operator does, the right is what the plant is doing, so the controls and the
        answer to "is it OK?" share a line and the faults are always one click away.
        """
        self.start_button = QPushButton("Start")
        set_property(self.start_button, "variant", "primary")
        self.start_button.setToolTip("Play the run from where it is.")
        self.pause_button = QPushButton("Pause")
        self.reset_button = QPushButton("Reset")
        self.reset_button.setToolTip("Go back to the start of the run. Faults and alarms are cleared.")
        self.start_button.clicked.connect(self._on_start_clicked)
        self.pause_button.clicked.connect(self._on_pause_clicked)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.speed_box = QComboBox()
        for speed in SPEEDS:
            self.speed_box.addItem(f"{speed:g}x", speed)
        self.speed_box.setToolTip("How many times faster than real time the run plays.")
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
        self.clear_faults_button.setToolTip("Remove every injected fault. The state returns to Normal.")
        self.clear_faults_button.clicked.connect(self._on_clear_clicked)

        for button in (self.pause_button, self.reset_button, self.clear_faults_button, *self.fault_buttons.values()):
            set_property(button, "variant", "tool")  # flat until hovered, like an editor's toolbar
        for button in (self.start_button, self.pause_button, self.reset_button, self.clear_faults_button,
                       *self.fault_buttons.values()):
            button.setProperty("compact", "true")

        toolbar = QFrame()
        toolbar.setProperty("card", "true")
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(4)
        for widget in (self.start_button, self.pause_button, self.reset_button):
            row.addWidget(widget)
        row.addWidget(vertical_separator())
        row.addWidget(self.speed_box)
        row.addWidget(self.time_label)
        row.addWidget(vertical_separator())
        row.addWidget(role_label("Inject", "muted"))
        for button in self.fault_buttons.values():
            row.addWidget(button)
        row.addWidget(self.clear_faults_button)
        row.addWidget(vertical_separator())
        row.addWidget(self.summary_label, 1)
        row.addWidget(self.banner)
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

    def _show_sample(self, sample: Sample) -> None:
        readings = format_readings(sample)
        self.plant.set_values(readings)
        self.twin.set_values(readings)
        self.banner.show_state(sample.state)
        self.gauge.show_deviation(sample.deviation_pct, sample.state)
        self.deviation_tile.set_text(f"{format_number(sample.deviation_pct, 1, signed=True)} %")
        self.time_label.setText(np.datetime_as_string(sample.timestamp, unit="m").replace("T", " "))
        sentence, detail = describe_state(sample, self._controller.config.thresholds)
        self.summary_label.setText(sentence)
        self.summary_label.setToolTip(detail)
        for kind, button in self.fault_buttons.items():
            set_property(button, "variant", "active" if kind in sample.active_faults else "tool")
        self.trend.add_sample(sample)

    def _show_start(self) -> None:
        self.banner.show_state(None)
        self.gauge.set_thresholds(self._controller.config.thresholds)
        self.plant.clear()
        self.twin.clear()
        self.gauge.clear()
        self.deviation_tile.clear()
        self.time_label.setText(PLACEHOLDER)
        self.summary_label.setText(IDLE_SENTENCE)
        self.summary_label.setToolTip(IDLE_DETAIL)
        for button in self.fault_buttons.values():
            set_property(button, "variant", "tool")
        self.trend.clear()
