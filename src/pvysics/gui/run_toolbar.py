"""The run toolbar: run controls, speed and clock, and fault injection, as one row.

The left is what the operator does, the right is what the plant is doing, so the controls and the faults are
always one click away. It drives the PlaybackController and follows the DataBus: the clock shows the current
sample, and a fault that is on shows as an active button. The HMI's Process view and the simple window share it.
"""

import numpy as np
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from pvysics.faults import FaultKind, default_fault
from pvysics.gui.data_bus import DataBus
from pvysics.gui.live_controller import LiveController
from pvysics.gui.playback import SPEEDS, PlaybackController
from pvysics.gui.ui_helpers import role_label, set_property, vertical_separator
from pvysics.run import Sample

PLACEHOLDER = "-"
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


class RunToolbar(QWidget):
    """Start, Pause, Reset, speed and clock on the left; fault buttons and Clear all on the right."""

    def __init__(
        self,
        controller: PlaybackController,
        bus: DataBus,
        parent: QWidget | None = None,
        live: LiveController | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._live = live
        self._live_active = False
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

        row = QHBoxLayout(self)
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

        bus.sample.connect(self._show_sample)
        bus.run_reset.connect(self._show_start)
        controller.running_changed.connect(self._on_running_changed)
        if live is not None:
            live.active_changed.connect(self.set_live)
            self._live_active = live.is_active
        self.refresh_controls()

    def set_live(self, active: bool) -> None:
        """While a live feed is the source, the controls of a simulated run do nothing: they are disabled."""
        self._live_active = active
        self.refresh_controls()

    def refresh_controls(self) -> None:
        running = self._controller.is_running
        simulated = not self._live_active
        self.start_button.setEnabled(simulated and not running and not self._controller.is_finished)
        self.pause_button.setEnabled(simulated and running)
        self.reset_button.setEnabled(simulated)
        self.speed_box.setEnabled(simulated)
        self.clear_faults_button.setEnabled(simulated)
        for button in self.fault_buttons.values():
            button.setEnabled(simulated)
        note = "A live feed is the source: readings arrive in real time, so the run cannot be controlled here." if not simulated else ""
        for widget in (self.start_button, self.speed_box):
            widget.setToolTip(note or ("Playback speed" if widget is self.speed_box else ""))

    def _on_fault_clicked(self, *_args) -> None:
        kind = FaultKind[self.sender().property("kind")]
        self._controller.inject(default_fault(kind))

    def _on_clear_clicked(self, *_args) -> None:
        self._controller.clear_faults()

    def _on_start_clicked(self, *_args) -> None:
        if self._live is not None and self._live.has_data:
            self._controller.reset()  # a simulated run starts afresh: it must not be appended to a feed's readings
        self._controller.start()

    def _on_pause_clicked(self, *_args) -> None:
        self._controller.pause()

    def _on_reset_clicked(self, *_args) -> None:
        self._controller.reset()

    def _on_speed_chosen(self, index: int) -> None:
        self._controller.set_speed(self.speed_box.itemData(index))

    def _on_running_changed(self, _running: bool) -> None:
        self.refresh_controls()

    def _show_sample(self, sample: Sample) -> None:
        self.time_label.setText(np.datetime_as_string(sample.timestamp, unit="m").replace("T", " "))
        for kind, button in self.fault_buttons.items():
            set_property(button, "variant", "active" if kind in sample.active_faults else "tool")

    def _show_start(self) -> None:
        self.time_label.setText(PLACEHOLDER)
        for button in self.fault_buttons.values():
            set_property(button, "variant", "tool")
