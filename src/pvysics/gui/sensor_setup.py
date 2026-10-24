"""The Sensors window's Setup tab: the simulated plant that stands in for hardware, and where a hardware feed connects.

Simulated plant: how far the plant's module differs from the twin's datasheet (mismatch) and how its sensors
misread (noise and quantisation), with the random seed. Applying starts a new run, like the HMI's Setup.

Source: where the readings come from. The simulated plant is the only source that works today. The hardware
kinds (serial, MQTT, HTTP or WebSocket) show the connection the feed will need and the channel names it must
carry, and Connect checks them; there is no driver behind it yet, and it says so rather than pretend.
"""

import logging
from dataclasses import replace

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pvysics.gui.setup_view import MAX_SEED, _fit, _roomy, _spin
from pvysics.gui.theme import ERROR_ROLE
from pvysics.gui.ui_helpers import role_label, set_property, unit_row
from pvysics.run import Mismatch, RunConfig, SensorModel
from pvysics.run_setup import validate_config

log = logging.getLogger(__name__)

SIMULATED = "Simulated plant"
SERIAL = "Serial port"
MQTT = "MQTT broker"
HTTP = "HTTP or WebSocket"
SOURCES = (SIMULATED, SERIAL, MQTT, HTTP)
BAUD_RATES = (9600, 19200, 38400, 57600, 115200)
DEFAULT_CHANNELS = (  # (channel, unit, the field name the feed uses for it)
    ("Irradiance", "W/m²", "irradiance"),
    ("Module temperature", "°C", "temperature"),
    ("Voltage", "V", "voltage"),
    ("Current", "A", "current"),
)
NOT_AVAILABLE = "No hardware driver in this version. The simulated plant stays the source."
PAGE_MAX_WIDTH_PX = 760


class SensorSetupView(QWidget):
    """The Setup tab. Emits connection_changed(text) with the hardware line the Sensors header shows."""

    connection_changed = pyqtSignal(str)

    def __init__(self, session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._applied: tuple[Mismatch, SensorModel, int] | None = None
        self._build()
        self._fill(session.config)
        session.config_changed.connect(self._on_config_changed)

    # --- the simulated plant -------------------------------------------------------------------

    def read_plant(self) -> tuple[Mismatch, SensorModel, int]:
        """The mismatch, the sensor model and the seed the controls describe."""
        mismatch = Mismatch(
            series_resistance_pct=self.rs_spin.value(),
            shunt_resistance_pct=self.rsh_spin.value(),
            temperature_coefficient_pct=self.temperature_coefficient_spin.value(),
        )
        sensors = SensorModel(
            irradiance_noise_pct=self.irradiance_noise_spin.value(),
            temperature_noise_c=self.temperature_noise_spin.value(),
            voltage_noise_v=self.voltage_noise_spin.value(),
            current_noise_a=self.current_noise_spin.value(),
            voltage_step_v=self.voltage_step_spin.value(),
            current_step_a=self.current_step_spin.value(),
        )
        return mismatch, sensors, self.seed_spin.value()

    @property
    def message(self) -> str:
        return self.message_label.text()

    @property
    def has_unapplied_changes(self) -> bool:
        return self._applied is not None and self.read_plant() != self._applied

    def apply(self) -> None:
        """Check the plant, then start a new run with it. The rest of the setup is the run's current one."""
        mismatch, sensors, seed = self.read_plant()
        config = replace(self._session.config, mismatch=mismatch, sensors=sensors, seed=seed)
        problems = validate_config(config)
        if problems:
            self._warn("Not applied. " + " ".join(problems))
            return
        self._say("Applied. New run started.")
        log.info("Simulated plant applied: Rs %+g %%, Rsh %+g %%, seed %d", mismatch.series_resistance_pct,
                 mismatch.shunt_resistance_pct, seed)
        self._session.apply_config(config)

    def reset_plant(self) -> None:
        """Show the default plant again. Applies nothing."""
        self._show_plant(Mismatch(), SensorModel(), 0)
        self._say("Defaults restored.")

    # --- the source ---------------------------------------------------------------------------

    @property
    def source(self) -> str:
        return self.source_box.currentText()

    def connect_source(self) -> None:
        """Check the chosen source's connection settings. Only the simulated plant can actually be used."""
        problems = self.connection_problems()
        if problems:
            self._warn("Not connected. " + " ".join(problems))
            return
        if self.source == SIMULATED:
            self._say("Using the simulated plant.")
            self.connection_changed.emit("")
            return
        self._warn(NOT_AVAILABLE)
        self.connection_changed.emit(f"{self.source}: not available yet")

    def connection_problems(self) -> list[str]:
        """What is missing from the chosen source's settings, in plain words."""
        source = self.source
        problems = []
        if source == SERIAL and not self.port_edit.text().strip():
            problems.append("Enter the serial port, for example /dev/ttyUSB0 or COM3.")
        if source == MQTT:
            if not self.host_edit.text().strip():
                problems.append("Enter the broker's host name.")
            if not self.topic_edit.text().strip():
                problems.append("Enter the topic the plant publishes on.")
        if source == HTTP:
            url = self.url_edit.text().strip()
            if not url.startswith(("http://", "https://", "ws://", "wss://")):
                problems.append("The address must start with http://, https://, ws:// or wss://.")
        if source != SIMULATED:
            names = [edit.text().strip() for edit in self.channel_edits.values()]
            if not all(names):
                problems.append("Every channel needs a field name.")
            elif len(set(names)) != len(names):
                problems.append("Each channel needs its own field name.")
        return problems

    # --- building -----------------------------------------------------------------------------

    def _build(self) -> None:
        self.rs_spin = _spin(-90.0, 500.0, 1)
        self.rsh_spin = _spin(-90.0, 500.0, 1)
        self.temperature_coefficient_spin = _spin(-90.0, 500.0, 1)
        self.irradiance_noise_spin = _spin(0.0, 20.0, 2)
        self.temperature_noise_spin = _spin(0.0, 10.0, 2)
        self.voltage_noise_spin = _spin(0.0, 1.0, 4)
        self.current_noise_spin = _spin(0.0, 5.0, 4)
        self.voltage_step_spin = _spin(0.0, 1.0, 4)
        self.current_step_spin = _spin(0.0, 1.0, 4)
        self.seed_spin = QSpinBox()
        _fit(self.seed_spin)
        self.seed_spin.setRange(0, MAX_SEED)
        for spin in self._plant_spins():
            spin.valueChanged.connect(self._update_dirty)

        mismatch_group = QGroupBox("Plant against twin")
        mismatch_group.setToolTip("How far the simulated module differs from the datasheet the twin uses.")
        form = QFormLayout(mismatch_group)
        _roomy(form)
        form.addRow("Rs offset", unit_row(self.rs_spin, "%"))
        form.addRow("Rsh offset", unit_row(self.rsh_spin, "%"))
        form.addRow("Temperature-coefficient offset", unit_row(self.temperature_coefficient_spin, "%"))

        sensor_group = QGroupBox("Sensor model")
        form = QFormLayout(sensor_group)
        _roomy(form)
        form.addRow("Irradiance noise", unit_row(self.irradiance_noise_spin, "%"))
        form.addRow("Temperature noise", unit_row(self.temperature_noise_spin, "°C"))
        form.addRow("Voltage noise", unit_row(self.voltage_noise_spin, "V"))
        form.addRow("Current noise", unit_row(self.current_noise_spin, "A"))
        form.addRow("Voltage quantisation", unit_row(self.voltage_step_spin, "V"))
        form.addRow("Current quantisation", unit_row(self.current_step_spin, "A"))
        form.addRow("Seed", self.seed_spin)

        self.source_box = QComboBox()
        self.source_box.addItems(SOURCES)
        self.source_box.currentIndexChanged.connect(self._on_source_chosen)
        self.port_edit = QLineEdit()
        self.port_edit.setPlaceholderText("/dev/ttyUSB0 or COM3")
        self.baud_box = QComboBox()
        for rate in BAUD_RATES:
            self.baud_box.addItem(str(rate), rate)
        self.baud_box.setCurrentIndex(self.baud_box.findData(115200))
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("broker.local")
        self.mqtt_port_spin = QSpinBox()
        self.mqtt_port_spin.setRange(1, 65535)
        self.mqtt_port_spin.setValue(1883)
        _fit(self.mqtt_port_spin)
        self.topic_edit = QLineEdit("pvysics/plant")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("ws://192.168.1.20:81/feed")

        self.connection_pages = QStackedWidget()
        self.connection_pages.addWidget(QWidget())  # the simulated plant has nothing to connect
        serial = QWidget()
        form = QFormLayout(serial)
        _roomy(form)
        form.addRow("Port", self.port_edit)
        form.addRow("Baud rate", self.baud_box)
        self.connection_pages.addWidget(serial)
        mqtt = QWidget()
        form = QFormLayout(mqtt)
        _roomy(form)
        form.addRow("Host", self.host_edit)
        form.addRow("Port", self.mqtt_port_spin)
        form.addRow("Topic", self.topic_edit)
        self.connection_pages.addWidget(mqtt)
        http = QWidget()
        form = QFormLayout(http)
        _roomy(form)
        form.addRow("Address", self.url_edit)
        self.connection_pages.addWidget(http)

        self.channel_edits: dict[str, QLineEdit] = {}
        self.channels_group = QGroupBox("Channels")
        self.channels_group.setToolTip("The field name each reading arrives under in the feed.")
        form = QFormLayout(self.channels_group)
        _roomy(form)
        for channel, unit, field in DEFAULT_CHANNELS:
            edit = QLineEdit(field)
            self.channel_edits[channel] = edit
            form.addRow(channel, unit_row(edit, unit))

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self._on_connect_clicked)
        source_group = QGroupBox("Connection")
        source_layout = QVBoxLayout(source_group)
        pick = QFormLayout()
        _roomy(pick)
        pick.addRow("Readings come from", self.source_box)
        source_layout.addLayout(pick)
        source_layout.addWidget(self.connection_pages)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.connect_button)
        source_layout.addLayout(row)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.dirty_label = role_label("", "muted")
        self.reset_button = QPushButton("Reset to defaults")
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.apply_button = QPushButton("Apply and start")
        set_property(self.apply_button, "variant", "primary")
        self.apply_button.setToolTip("Start a new run from the beginning with this plant.")
        self.apply_button.clicked.connect(self._on_apply_clicked)

        column = QWidget()
        column.setMaximumWidth(PAGE_MAX_WIDTH_PX)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(8, 12, 8, 16)
        layout.setSpacing(14)
        layout.addWidget(role_label("Source", "title"))
        layout.addWidget(source_group)
        layout.addWidget(self.channels_group)
        layout.addWidget(role_label("Simulated plant", "title"))
        layout.addWidget(mismatch_group)
        layout.addWidget(sensor_group)
        layout.addStretch(1)
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(column, 100)
        outer.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)

        actions = QHBoxLayout()
        actions.addWidget(self.message_label, 1)
        actions.addWidget(self.dirty_label)
        actions.addSpacing(8)
        actions.addWidget(self.reset_button)
        actions.addWidget(self.apply_button)
        root = QVBoxLayout(self)
        root.addWidget(scroll, 1)
        root.addLayout(actions)
        self._on_source_chosen(0)

    def _plant_spins(self):
        return (
            self.rs_spin, self.rsh_spin, self.temperature_coefficient_spin, self.irradiance_noise_spin,
            self.temperature_noise_spin, self.voltage_noise_spin, self.current_noise_spin, self.voltage_step_spin,
            self.current_step_spin, self.seed_spin,
        )

    def _show_plant(self, mismatch: Mismatch, sensors: SensorModel, seed: int) -> None:
        self.rs_spin.setValue(mismatch.series_resistance_pct)
        self.rsh_spin.setValue(mismatch.shunt_resistance_pct)
        self.temperature_coefficient_spin.setValue(mismatch.temperature_coefficient_pct)
        self.irradiance_noise_spin.setValue(sensors.irradiance_noise_pct)
        self.temperature_noise_spin.setValue(sensors.temperature_noise_c)
        self.voltage_noise_spin.setValue(sensors.voltage_noise_v)
        self.current_noise_spin.setValue(sensors.current_noise_a)
        self.voltage_step_spin.setValue(sensors.voltage_step_v)
        self.current_step_spin.setValue(sensors.current_step_a)
        self.seed_spin.setValue(seed)

    def _fill(self, config: RunConfig) -> None:
        self._show_plant(config.mismatch, config.sensors, config.seed)
        self._applied = self.read_plant()
        self._update_dirty()

    def _on_config_changed(self, config: RunConfig) -> None:
        """A run was applied (here or in the HMI): the controls and what counts as applied follow it."""
        self._fill(config)

    def _update_dirty(self, *_args) -> None:
        if self._applied is None:
            return
        dirty = self.has_unapplied_changes
        self.dirty_label.setText("Changes not applied yet" if dirty else "Matches the current run")
        set_property(self.dirty_label, "role", "dirty" if dirty else "muted")

    def _on_source_chosen(self, index: int) -> None:
        self.connection_pages.setCurrentIndex(index)
        hardware = self.source != SIMULATED
        self.channels_group.setVisible(hardware)
        self.connect_button.setText("Connect" if hardware else "Use simulated plant")

    def _on_connect_clicked(self, *_args) -> None:
        self.connect_source()

    def _on_apply_clicked(self, *_args) -> None:
        self.apply()

    def _on_reset_clicked(self, *_args) -> None:
        self.reset_plant()

    def _say(self, text: str, error: bool = False) -> None:
        self.message_label.setText(text)
        self.message_label.setForegroundRole(ERROR_ROLE if error else QPalette.ColorRole.WindowText)

    def _warn(self, text: str) -> None:
        self._say(text, error=True)
        log.warning(text)
