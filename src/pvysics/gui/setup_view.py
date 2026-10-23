"""The HMI Setup view: the inputs of the next run. Nothing here takes effect until Apply and start.

Layout follows the setup wireframe: input profile, module and site on the left, plant mismatch,
sensor model and seed in the middle, state thresholds and the run summary on the right, and the
actions along the bottom. A CSV is loaded through ProfileDialog, which maps its columns and shows
the file checks. Apply and start hands a validated RunConfig to the window, which starts the run.
"""

import logging
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QSignalBlocker, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pvysics.datasheet import (
    DatasheetError,
    ModuleDatasheet,
    edited_datasheet,
    load_generic_datasheet,
)
from pvysics.datasheet import load_datasheet as read_datasheet
from pvysics.profile import (
    BUNDLED_DAYS,
    NASA_COLUMNS,
    NASA_TIMESTAMP,
    ColumnMap,
    Profile,
    ProfileError,
    csv_columns,
    guess_columns,
    load_bundled_profile,
    parse_profile_table,
)
from pvysics.gui.fetch_panel import FetchPanel
from pvysics.gui.theme import ERROR_ROLE, ThemeManager
from pvysics.run import Mismatch, RunConfig, SensorModel, Site, Thresholds, bundled_run_config
from pvysics.run_setup import datasheet_problems, derive_thresholds, summary_rows, validate_config

log = logging.getLogger(__name__)
NO_COLUMN = "(choose a column)"
MAX_SEED = 2**31 - 1  # the seed spin box is a 32-bit integer
MAX_CELLS = 100000  # the Ns spin box: cells in series


def _spin(low: float, high: float, decimals: int, suffix: str = "") -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(low, high)
    spin.setDecimals(decimals)
    spin.setSingleStep(10.0**-decimals)
    spin.setSuffix(suffix)
    return spin


def _summary(config: RunConfig) -> str:
    """One line on the log: what the applied setup is."""
    thresholds = config.thresholds
    return (
        f"profile {config.profile.name}, module {config.datasheet.name}, seed {config.seed}, "
        f"warning {thresholds.warning_pct:g} %, abnormal {thresholds.abnormal_pct:g} %"
    )


def _stamp(stamp: np.datetime64) -> str:
    return np.datetime_as_string(stamp, unit="m").replace("T", " ")


def _column_box(header: list[str], guessed: str, nasa: bool = False) -> QComboBox:
    """A list of the header columns. The guessed column is selected; nothing is selected when no column matched."""
    box = QComboBox()
    box.addItem(NO_COLUMN, "")
    for column in header:
        box.addItem(column, column)
    if nasa and all(column in header for column in NASA_COLUMNS):
        box.addItem("YEAR, MO, DY, HR (NASA POWER)", NASA_TIMESTAMP)
    box.setCurrentIndex(max(box.findData(guessed), 0))
    return box


class ProfileDialog(QDialog):
    """Column mapping and file checks for a CSV profile. Use profile is enabled only when the file passes."""

    def __init__(self, file_name: str, text: str, header: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Load profile: {file_name}")
        self._file_name = file_name
        self._text = text
        self._profile: Profile | None = None
        guess = guess_columns(header)

        self.timestamp_box = _column_box(header, guess.timestamp, nasa=True)
        self.irradiance_box = _column_box(header, guess.irradiance)
        self.temperature_box = _column_box(header, guess.temperature)
        mapping = QFormLayout()
        mapping.addRow("Timestamp", self.timestamp_box)
        mapping.addRow("Irradiance G", self.irradiance_box)
        mapping.addRow("Temperature T", self.temperature_box)

        self.checks_label = QLabel()
        self.checks_label.setWordWrap(True)
        buttons = QDialogButtonBox()
        self.use_button = buttons.addButton("Use profile", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{file_name}: map the columns, then check the file."))
        layout.addLayout(mapping)
        layout.addWidget(self.checks_label)
        layout.addWidget(buttons)
        for box in (self.timestamp_box, self.irradiance_box, self.temperature_box):
            box.currentIndexChanged.connect(self._check)
        self._check()

    def profile(self) -> Profile | None:
        """The profile the file gives with the chosen columns, or None when the checks fail."""
        return self._profile

    def _check(self, *_args) -> None:
        columns = ColumnMap(
            timestamp=self.timestamp_box.currentData() or "",
            irradiance=self.irradiance_box.currentData() or "",
            temperature=self.temperature_box.currentData() or "",
        )
        try:
            profile = parse_profile_table(self._text, columns, name=self._file_name)
        except ProfileError as error:
            self._profile = None
            log.warning("Profile %s rejected: %s", self._file_name, error)
            self.checks_label.setText(f"Rejected: {error}. The previous profile stays active.")
            self.checks_label.setForegroundRole(ERROR_ROLE)
            self.use_button.setEnabled(False)
            return
        self._profile = profile
        step = (profile.timestamps[1] - profile.timestamps[0]) / np.timedelta64(1, "s")
        self.checks_label.setText(
            f"Passed: {len(profile.timestamps)} rows from {_stamp(profile.timestamps[0])} "
            f"to {_stamp(profile.timestamps[-1])}, time step {step:g} s."
        )
        self.checks_label.setForegroundRole(QPalette.ColorRole.WindowText)
        self.use_button.setEnabled(True)


class SetupView(QWidget):
    """The Setup screen. Holds the controls for the next run and emits apply_requested with a validated RunConfig.

    The window connects to apply_requested. A signal, not a callback, keeps the window out of a Python reference cycle.
    """

    apply_requested = pyqtSignal(object)  # RunConfig

    def __init__(self, config: RunConfig, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme  # the fetch preview is themed from it
        self._profiles: dict[str, Profile] = {}
        for day in BUNDLED_DAYS:
            profile = load_bundled_profile(day)
            self._profiles[profile.name] = profile
        self._profile = config.profile
        self._datasheet = config.datasheet  # the module the module fields were last set from
        self._shown_module: dict[str, float | int] = {}  # the module values the fields showed then
        self.csv_dialog: ProfileDialog | None = None
        self._build()
        self._fill(config)
        self._show_summary(config)

    @property
    def profile_name(self) -> str:
        """The name of the profile the controls currently select."""
        return self._profile.name

    @property
    def datasheet_name(self) -> str:
        return self._current_datasheet().name

    @property
    def message(self) -> str:
        return self.message_label.text()

    def read_config(self) -> RunConfig:
        """The RunConfig the controls describe. Faults are none: a new run starts without them."""
        return RunConfig(
            profile=self._profile,
            datasheet=self._current_datasheet(),
            mismatch=Mismatch(
                series_resistance_pct=self.rs_spin.value(),
                shunt_resistance_pct=self.rsh_spin.value(),
                temperature_coefficient_pct=self.temperature_coefficient_spin.value(),
            ),
            sensors=SensorModel(
                irradiance_noise_pct=self.irradiance_noise_spin.value(),
                temperature_noise_c=self.temperature_noise_spin.value(),
                voltage_noise_v=self.voltage_noise_spin.value(),
                current_noise_a=self.current_noise_spin.value(),
                voltage_step_v=self.voltage_step_spin.value(),
                current_step_a=self.current_step_spin.value(),
            ),
            thresholds=Thresholds(
                warning_pct=self.warning_spin.value(),
                abnormal_pct=self.abnormal_spin.value(),
            ),
            seed=self.seed_spin.value(),
            site=Site(
                latitude_deg=self.latitude_spin.value(),
                longitude_deg=self.longitude_spin.value(),
                tilt_deg=self.tilt_spin.value(),
                azimuth_deg=self.azimuth_spin.value(),
            ),
        )

    def validate(self) -> list[str]:
        """Check the controls and report every problem. Starts nothing."""
        problems = validate_config(self.read_config())
        if problems:
            self._warn("Not valid. " + " ".join(problems))
        else:
            self._say("Setup is valid. Nothing changes until Apply and start.")
            log.info("Setup validated: valid")
        return problems

    def apply(self) -> None:
        """Validate, then hand the config to the window, which starts a new run from the beginning."""
        config = self.read_config()
        problems = validate_config(config)
        if problems:
            self._warn("Not applied. " + " ".join(problems))
            return
        self._show_summary(config)
        self._say("Applied. The new run has started from the beginning.")
        log.info("Setup applied: %s", _summary(config))
        self.apply_requested.emit(config)

    def reset_to_defaults(self) -> None:
        """Show the default setup again. Like every edit, this applies nothing."""
        self._fill(bundled_run_config())
        self._say("Controls reset to the defaults. Nothing changes until Apply and start.")

    def load_csv(self, path: str) -> None:
        """Open the column mapping for a CSV file. The profile changes only if the user accepts it."""
        file = Path(path)
        try:
            text = file.read_text(encoding="utf-8-sig")
            header = csv_columns(text)
        except (OSError, UnicodeDecodeError) as error:
            self._warn(f"{file.name}: cannot read the file as text ({error}). The profile is unchanged.")
            return
        except ProfileError as error:
            self._warn(f"{file.name}: {error}. The profile is unchanged.")
            return
        self.csv_dialog = ProfileDialog(file.name, text, header, parent=self)
        self.csv_dialog.accepted.connect(self._use_csv)
        self.csv_dialog.rejected.connect(self._cancel_csv)
        self.csv_dialog.open()

    def load_datasheet(self, path: str) -> None:
        """Read a module datasheet file. A malformed file is rejected and the module stays as it was."""
        try:
            datasheet = read_datasheet(path)
        except DatasheetError as error:
            self._warn(f"Datasheet rejected: {error}. The module is still {self._datasheet.name}.")
            return
        self._set_datasheet(datasheet)
        self._say(f"Loaded module {datasheet.name}. Apply and start to use it.")

    def _use_csv(self) -> None:
        profile = self.csv_dialog.profile()
        if profile is None:
            return
        self._set_profile(profile)
        self._say(f"Loaded {profile.name}: {len(profile.timestamps)} samples. Apply and start to use it.")

    def _cancel_csv(self) -> None:
        self._say("Load cancelled. The previous profile stays active.")

    def _use_fetched(self, profile: Profile) -> None:
        self._set_profile(profile)
        self._show_summary(self.read_config())  # the Run summary shows the profile the next Apply and start will use
        self._say(f"Using fetched {profile.name}: {len(profile.timestamps)} samples. Apply and start to use it.")

    def _show_fetch_message(self, text: str, problem: bool) -> None:
        self._say(text, error=problem)  # the fetch has already logged the problem at its level

    def _sync_fetch_site(self, *_args) -> None:
        """The fetch position follows the Site fields while Use Site location is checked."""
        self.fetch_panel.set_site(self.latitude_spin.value(), self.longitude_spin.value())

    def shutdown(self) -> None:
        """End a running fetch before the window closes. See FetchPanel.shutdown."""
        self.fetch_panel.shutdown()

    def _on_validate_clicked(self, *_args) -> None:
        self.validate()

    def _on_reset_clicked(self, *_args) -> None:
        self.reset_to_defaults()

    def _on_apply_clicked(self, *_args) -> None:
        self.apply()

    def _derive(self) -> None:
        problems = datasheet_problems(self._current_datasheet())
        if problems:  # the fit inside the derivation needs a valid module
            self._warn("Cannot derive the limits until the module is valid. " + " ".join(problems))
            return
        try:
            thresholds = derive_thresholds(self.read_config())
        except ValueError as error:
            self._warn(f"Cannot derive the limits: {error}.")
            return
        self.warning_spin.setValue(thresholds.warning_pct)
        self.abnormal_spin.setValue(thresholds.abnormal_pct)
        self._say(
            f"Derived from a healthy run: warning {self.warning_spin.value():.2f} %, "
            f"abnormal {self.abnormal_spin.value():.2f} %. Both stay editable."
        )

    def _choose_csv(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Load profile CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if path:
            self.load_csv(path)

    def _choose_datasheet(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Load module datasheet", "", "Module datasheets (*.json *.toml);;All files (*)"
        )
        if path:
            self.load_datasheet(path)

    def _reset_module(self) -> None:
        datasheet = load_generic_datasheet()
        self._set_datasheet(datasheet)
        self._say(f"Module reset to {datasheet.name}. Nothing changes until Apply and start.")

    def _on_profile_chosen(self, index: int) -> None:
        self._profile = self._profiles[self.profile_box.itemData(index)]
        self._show_profile()

    def _set_profile(self, profile: Profile) -> None:
        self._profiles[profile.name] = profile
        self._profile = profile
        if self.profile_box.findData(profile.name) < 0:
            self.profile_box.addItem(profile.name, profile.name)
        with QSignalBlocker(self.profile_box):
            self.profile_box.setCurrentIndex(self.profile_box.findData(profile.name))
        self._show_profile()

    def _set_datasheet(self, datasheet: ModuleDatasheet) -> None:
        """Show a module's values in the fields. Applies nothing."""
        self._datasheet = datasheet
        for field, spin in self._module_spins.items():
            spin.setValue(getattr(datasheet, field))
        self._shown_module = self._module_values()  # read back, so the spin boxes' rounding is not an edit
        self._show_module_name()

    def _module_values(self) -> dict[str, float | int]:
        return {field: spin.value() for field, spin in self._module_spins.items()}

    def _current_datasheet(self) -> ModuleDatasheet:
        """The module the fields describe: the module last shown, or a custom copy once a field has been edited."""
        values = self._module_values()
        if values == self._shown_module:
            return self._datasheet
        return edited_datasheet(self._datasheet, **values)

    def _show_module_name(self, *_args) -> None:
        self.module_label.setText(f"Module: {self._current_datasheet().name}")

    def _show_profile(self) -> None:
        profile = self._profile
        self.profile_info.setText(
            f"{len(profile.timestamps)} samples, {_stamp(profile.timestamps[0])} "
            f"to {_stamp(profile.timestamps[-1])}"
        )

    def _show_summary(self, config: RunConfig) -> None:
        self.summary_label.setText("\n".join(f"{label}: {value}" for label, value in summary_rows(config)))

    def _fill(self, config: RunConfig) -> None:
        """Show every control with the values of config. Applies nothing."""
        self._set_profile(config.profile)
        self._set_datasheet(config.datasheet)
        mismatch, sensors = config.mismatch, config.sensors
        thresholds, site = config.thresholds, config.site
        self.rs_spin.setValue(mismatch.series_resistance_pct)
        self.rsh_spin.setValue(mismatch.shunt_resistance_pct)
        self.temperature_coefficient_spin.setValue(mismatch.temperature_coefficient_pct)
        self.irradiance_noise_spin.setValue(sensors.irradiance_noise_pct)
        self.temperature_noise_spin.setValue(sensors.temperature_noise_c)
        self.voltage_noise_spin.setValue(sensors.voltage_noise_v)
        self.current_noise_spin.setValue(sensors.current_noise_a)
        self.voltage_step_spin.setValue(sensors.voltage_step_v)
        self.current_step_spin.setValue(sensors.current_step_a)
        self.seed_spin.setValue(config.seed)
        self.warning_spin.setValue(thresholds.warning_pct)
        self.abnormal_spin.setValue(thresholds.abnormal_pct)
        self.latitude_spin.setValue(site.latitude_deg)
        self.longitude_spin.setValue(site.longitude_deg)
        self.tilt_spin.setValue(site.tilt_deg)
        self.azimuth_spin.setValue(site.azimuth_deg)

    def _say(self, text: str, error: bool = False) -> None:
        self.message_label.setText(text)
        self.message_label.setForegroundRole(ERROR_ROLE if error else QPalette.ColorRole.WindowText)

    def _warn(self, text: str) -> None:
        """A problem: shown in the error colour and logged as a warning with the same text."""
        self._say(text, error=True)
        log.warning(text)

    def _build(self) -> None:
        self.profile_box = QComboBox()
        for name in self._profiles:
            self.profile_box.addItem(name, name)
        self.profile_box.currentIndexChanged.connect(self._on_profile_chosen)
        self.profile_info = QLabel()
        self.profile_info.setWordWrap(True)
        self.load_csv_button = QPushButton("Load CSV...")
        self.load_csv_button.clicked.connect(self._choose_csv)
        self.fetch_panel = FetchPanel(self._theme, self)
        self.fetch_panel.message.connect(self._show_fetch_message)
        self.fetch_panel.profile_chosen.connect(self._use_fetched)

        self.module_label = QLabel()
        self.module_label.setWordWrap(True)
        self.isc_spin = _spin(0.0, 10000.0, 2)
        self.voc_spin = _spin(0.0, 10000.0, 2)
        self.impp_spin = _spin(0.0, 10000.0, 2)
        self.vmpp_spin = _spin(0.0, 10000.0, 2)
        self.ki_spin = _spin(-100.0, 100.0, 3)
        self.kv_spin = _spin(-100.0, 100.0, 3)
        self.ns_spin = QSpinBox()
        self.ns_spin.setRange(0, MAX_CELLS)
        self._module_spins = {
            "isc_a": self.isc_spin,
            "voc_v": self.voc_spin,
            "impp_a": self.impp_spin,
            "vmpp_v": self.vmpp_spin,
            "ki_pct_per_c": self.ki_spin,
            "kv_pct_per_c": self.kv_spin,
            "ns": self.ns_spin,
        }
        for spin in self._module_spins.values():
            spin.valueChanged.connect(self._show_module_name)
        self.load_datasheet_button = QPushButton("Load datasheet...")
        self.load_datasheet_button.clicked.connect(self._choose_datasheet)
        self.reset_module_button = QPushButton("Reset to generic module")
        self.reset_module_button.clicked.connect(self._reset_module)

        self.rs_spin = _spin(-90.0, 500.0, 1, " %")
        self.rsh_spin = _spin(-90.0, 500.0, 1, " %")
        self.temperature_coefficient_spin = _spin(-90.0, 500.0, 1, " %")
        self.irradiance_noise_spin = _spin(0.0, 20.0, 2, " %")
        self.temperature_noise_spin = _spin(0.0, 10.0, 2, " °C")
        self.voltage_noise_spin = _spin(0.0, 1.0, 4, " V")
        self.current_noise_spin = _spin(0.0, 5.0, 4, " A")
        self.voltage_step_spin = _spin(0.0, 1.0, 4, " V")
        self.current_step_spin = _spin(0.0, 1.0, 4, " A")
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, MAX_SEED)
        self.warning_spin = _spin(0.01, 200.0, 2, " %")
        self.abnormal_spin = _spin(0.01, 200.0, 2, " %")
        self.derive_button = QPushButton("Derive from healthy run")
        self.derive_button.clicked.connect(self._derive)
        self.latitude_spin = _spin(-90.0, 90.0, 2, " °")
        self.longitude_spin = _spin(-180.0, 180.0, 2, " °")
        self.tilt_spin = _spin(0.0, 90.0, 1, " °")
        self.azimuth_spin = _spin(0.0, 360.0, 1, " ° (0 is north)")
        self.latitude_spin.valueChanged.connect(self._sync_fetch_site)
        self.longitude_spin.valueChanged.connect(self._sync_fetch_site)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.TextFormat.PlainText)
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.validate_button = QPushButton("Validate setup")
        self.validate_button.clicked.connect(self._on_validate_clicked)
        self.reset_button = QPushButton("Reset to defaults")
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.apply_button = QPushButton("Apply and start")
        self.apply_button.clicked.connect(self._on_apply_clicked)

        profile_group = QGroupBox("Input profile")
        layout = QVBoxLayout(profile_group)
        layout.addWidget(self.profile_box)
        layout.addWidget(self.load_csv_button)
        layout.addWidget(self.profile_info)

        module_group = QGroupBox("Module datasheet")
        layout = QVBoxLayout(module_group)
        layout.addWidget(self.module_label)
        form = QFormLayout()
        form.addRow("Isc (A)", self.isc_spin)
        form.addRow("Voc (V)", self.voc_spin)
        form.addRow("Impp (A)", self.impp_spin)
        form.addRow("Vmpp (V)", self.vmpp_spin)
        form.addRow("Ki (%/C)", self.ki_spin)
        form.addRow("Kv (%/C)", self.kv_spin)
        form.addRow("Ns (cells)", self.ns_spin)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addWidget(self.load_datasheet_button)
        buttons.addWidget(self.reset_module_button)
        layout.addLayout(buttons)

        site_group = QGroupBox("Site (metadata only, does not change the physics)")
        form = QFormLayout(site_group)
        form.addRow("Latitude", self.latitude_spin)
        form.addRow("Longitude", self.longitude_spin)
        form.addRow("Tilt", self.tilt_spin)
        form.addRow("Azimuth", self.azimuth_spin)

        mismatch_group = QGroupBox("Plant vs twin mismatch")
        form = QFormLayout(mismatch_group)
        form.addRow("Rs offset", self.rs_spin)
        form.addRow("Rsh offset", self.rsh_spin)
        form.addRow("Temperature-coefficient offset", self.temperature_coefficient_spin)

        sensor_group = QGroupBox("Sensor model")
        form = QFormLayout(sensor_group)
        form.addRow("Irradiance noise", self.irradiance_noise_spin)
        form.addRow("Temperature noise", self.temperature_noise_spin)
        form.addRow("Voltage noise", self.voltage_noise_spin)
        form.addRow("Current noise", self.current_noise_spin)
        form.addRow("Voltage quantisation", self.voltage_step_spin)
        form.addRow("Current quantisation", self.current_step_spin)
        form.addRow("Seed", self.seed_spin)

        threshold_group = QGroupBox("State thresholds")
        form = QFormLayout(threshold_group)
        form.addRow("Warning limit", self.warning_spin)
        form.addRow("Abnormal limit", self.abnormal_spin)
        form.addRow(self.derive_button)

        summary_group = QGroupBox("Run summary")
        QVBoxLayout(summary_group).addWidget(self.summary_label)

        columns = QHBoxLayout()
        for column in (
            (profile_group, self.fetch_panel, module_group, site_group),
            (mismatch_group, sensor_group),
            (threshold_group, summary_group),
        ):
            side = QVBoxLayout()
            for group in column:
                side.addWidget(group)
            side.addStretch(1)
            columns.addLayout(side, 1)

        actions = QHBoxLayout()
        actions.addWidget(self.message_label, 1)
        for button in (self.validate_button, self.reset_button, self.apply_button):
            actions.addWidget(button)

        root = QVBoxLayout(self)
        root.addLayout(columns, 1)
        root.addLayout(actions)
