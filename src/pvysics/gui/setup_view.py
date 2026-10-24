"""The HMI Setup view: the inputs of the next run. Nothing here takes effect until Apply and start.

Layout follows the setup wireframe: input profile, module and site on the left, plant mismatch,
sensor model and seed in the middle, state thresholds and the run summary on the right, and the
actions along the bottom. A CSV is loaded through ProfileDialog, which maps its columns and shows
the file checks. Apply and start hands a validated RunConfig to the window, which starts the run.
"""

import csv
import html
import io
import itertools
import logging
from dataclasses import replace
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QSignalBlocker, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QAbstractItemView,
    QDoubleSpinBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QGridLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
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
from pvysics.gui.ui_helpers import role_label, set_property, unit_row
from pvysics.run import RunConfig, Site, Thresholds, bundled_run_config
from pvysics.run_setup import datasheet_problems, derive_thresholds, summary_rows, validate_config

log = logging.getLogger(__name__)
NO_COLUMN = "(choose a column)"
MAX_SEED = 2**31 - 1  # the seed spin box is a 32-bit integer
MAX_CELLS = 100000  # the Ns spin box: cells in series


FIELD_MIN_CHARS = 12  # a number field is at least this many digits wide, and never wider than FIELD_MAX_CHARS
FIELD_MAX_CHARS = 22
DIALOG_MIN_WIDTH_PX = 560
PREVIEW_ROWS = 5  # rows of the file the CSV dialog shows
PAGE_MAX_WIDTH_PX = 760  # a page reads as a column, not as fields stretched across the window
NAV_WIDTH_PX = 190


def _fit(spin: QDoubleSpinBox | QSpinBox) -> None:
    """Keep a number field to a sensible width: wide enough to read, not stretched across the page."""
    digit = spin.fontMetrics().horizontalAdvance("0")
    spin.setMinimumWidth(digit * FIELD_MIN_CHARS)
    spin.setMaximumWidth(digit * FIELD_MAX_CHARS)


def _align_labels(*forms: QFormLayout) -> None:
    """Give the forms one label column, so their fields start at the same place on a page."""
    widest = max(
        form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget().sizeHint().width()
        for form in forms
        for row in range(form.rowCount())
        if form.itemAt(row, QFormLayout.ItemRole.LabelRole) is not None
    )
    for form in forms:
        for row in range(form.rowCount()):
            label = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if label is not None:
                label.widget().setMinimumWidth(widest)


def _roomy(form: QFormLayout) -> None:
    """Give a form room: a gap between rows, a gap between label and field, labels on the left."""
    form.setVerticalSpacing(12)
    form.setHorizontalSpacing(20)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


def _spin(low: float, high: float, decimals: int) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    _fit(spin)
    spin.setRange(low, high)
    spin.setDecimals(decimals)
    spin.setSingleStep(10.0**-decimals)
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


def _preview_table(text: str, header: list[str]) -> QTableWidget:
    """The first rows of the file as a read-only table, so the user can see what the columns hold."""
    rows = list(itertools.islice(csv.reader(io.StringIO(text)), 1, 1 + PREVIEW_ROWS))
    table = QTableWidget(len(rows), len(header))
    table.setHorizontalHeaderLabels(header)
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row[: len(header)]):
            table.setItem(row_index, column_index, QTableWidgetItem(value))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setFixedHeight(
        table.horizontalHeader().sizeHint().height() + table.verticalHeader().defaultSectionSize() * max(len(rows), 1) + 6
    )
    return table


class ProfileDialog(QDialog):
    """Column mapping and file checks for a CSV profile. Use profile is enabled only when the file passes."""

    def __init__(self, file_name: str, text: str, header: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Load profile: {file_name}")
        self._file_name = file_name
        self._text = text
        self._profile: Profile | None = None
        guess = guess_columns(header)
        self.setMinimumWidth(DIALOG_MIN_WIDTH_PX)

        self.timestamp_box = _column_box(header, guess.timestamp, nasa=True)
        self.irradiance_box = _column_box(header, guess.irradiance)
        self.temperature_box = _column_box(header, guess.temperature)
        mapping = QFormLayout()
        _roomy(mapping)
        mapping.addRow("Timestamp", self.timestamp_box)
        mapping.addRow("Irradiance G", unit_row(self.irradiance_box, "W/m²"))
        mapping.addRow("Temperature T", unit_row(self.temperature_box, "°C"))

        self.preview_table = _preview_table(text, header)

        self.checks_label = QLabel()
        self.checks_label.setWordWrap(True)

        buttons = QDialogButtonBox()
        self.use_button = buttons.addButton("Use profile", QDialogButtonBox.ButtonRole.AcceptRole)
        set_property(self.use_button, "variant", "primary")
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(14)
        layout.addWidget(role_label(file_name, "title"))
        layout.addLayout(mapping)
        layout.addWidget(role_label("First rows", "section"))
        layout.addWidget(self.preview_table)
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
            self.checks_label.setText(f"Rejected: {error}")
            self.checks_label.setForegroundRole(ERROR_ROLE)
            self.use_button.setEnabled(False)
            return
        self._profile = profile
        step = (profile.timestamps[1] - profile.timestamps[0]) / np.timedelta64(1, "s")
        self.checks_label.setText(
            f"{len(profile.timestamps)} rows, {_stamp(profile.timestamps[0])} to {_stamp(profile.timestamps[-1])}, "
            f"step {step:g} s."
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
        self._plant = (config.mismatch, config.sensors, config.seed)  # set in the Sensors window, carried along here
        self._applied_config: RunConfig | None = None  # what the running run uses; None while building
        self._build()
        self._fill(config)
        self._show_summary(config)
        self._applied_config = config
        self._update_dirty()

    def follow_config(self, config: RunConfig) -> None:
        """A new run was applied somewhere (the Sensors window changes the plant): carry its plant settings along."""
        self._plant = (config.mismatch, config.sensors, config.seed)
        if self._applied_config is not None:
            self._applied_config = replace(
                self._applied_config, mismatch=config.mismatch, sensors=config.sensors, seed=config.seed
            )
        self._show_summary(self._applied_config or config)
        self._update_dirty()

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
        mismatch, sensors, seed = self._plant
        return RunConfig(
            profile=self._profile,
            datasheet=self._current_datasheet(),
            mismatch=mismatch,
            sensors=sensors,
            thresholds=Thresholds(
                warning_pct=self.warning_spin.value(),
                abnormal_pct=self.abnormal_spin.value(),
            ),
            seed=seed,
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
            self._say("Setup is valid.")
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
        self._applied_config = config
        self._update_dirty()
        self._say("Applied. New run started.")
        log.info("Setup applied: %s", _summary(config))
        self.apply_requested.emit(config)

    def reset_to_defaults(self) -> None:
        """Show the default setup again. Like every edit, this applies nothing."""
        self._fill(bundled_run_config())
        self._say("Defaults restored.")

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
            self._warn(f"Datasheet rejected: {error}")
            return
        self._set_datasheet(datasheet)
        self._say(f"Module {datasheet.name} loaded.")

    def _use_csv(self) -> None:
        profile = self.csv_dialog.profile()
        if profile is None:
            return
        self._set_profile(profile)
        self._say(f"{profile.name}: {len(profile.timestamps)} samples loaded.")

    def _cancel_csv(self) -> None:
        self._say("Load cancelled.")

    def _use_fetched(self, profile: Profile) -> None:
        self._set_profile(profile)
        self._show_summary(self.read_config())  # the Run summary shows the profile the next Apply and start will use
        self._say(f"Using {profile.name}: {len(profile.timestamps)} samples.")

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
        self._say(f"Module reset to {datasheet.name}.")

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
        """The Review page: what the next run uses, as a table of label and value."""
        rows = "".join(
            f"<tr><td style='padding: 5px 24px 5px 0;'><b>{html.escape(label)}</b></td>"
            f"<td style='padding: 5px 0;'>{html.escape(value)}</td></tr>"
            for label, value in summary_rows(config)
        )
        self.summary_label.setText(f"<table cellspacing='0'>{rows}</table>")

    def _fill(self, config: RunConfig) -> None:
        """Show every control with the values of config. Applies nothing."""
        self._set_profile(config.profile)
        self._set_datasheet(config.datasheet)
        thresholds, site = config.thresholds, config.site
        self.warning_spin.setValue(thresholds.warning_pct)
        self.abnormal_spin.setValue(thresholds.abnormal_pct)
        self.latitude_spin.setValue(site.latitude_deg)
        self.longitude_spin.setValue(site.longitude_deg)
        self.tilt_spin.setValue(site.tilt_deg)
        self.azimuth_spin.setValue(site.azimuth_deg)

    @property
    def has_unapplied_changes(self) -> bool:
        """True when the controls describe a run different from the one that is running."""
        return self._applied_config is not None and summary_rows(self.read_config()) != summary_rows(self._applied_config)

    def _update_dirty(self, *_args) -> None:
        """Show whether Apply and start would change anything, and call attention to Apply when it would."""
        if self._applied_config is None:
            return
        dirty = self.has_unapplied_changes
        self.dirty_label.setText("Changes not applied yet" if dirty else "Matches the current run")
        set_property(self.dirty_label, "role", "dirty" if dirty else "muted")
        set_property(self.apply_button, "variant", "primary")

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
        _fit(self.ns_spin)
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

        self.warning_spin = _spin(0.01, 200.0, 2)
        self.abnormal_spin = _spin(0.01, 200.0, 2)
        self.derive_button = QPushButton("Derive from healthy run")
        self.derive_button.clicked.connect(self._derive)
        self.latitude_spin = _spin(-90.0, 90.0, 2)
        self.longitude_spin = _spin(-180.0, 180.0, 2)
        self.tilt_spin = _spin(0.0, 90.0, 1)
        self.azimuth_spin = _spin(0.0, 360.0, 1)
        self.latitude_spin.valueChanged.connect(self._sync_fetch_site)
        self.longitude_spin.valueChanged.connect(self._sync_fetch_site)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.validate_button = QPushButton("Validate setup")
        self.validate_button.clicked.connect(self._on_validate_clicked)
        self.reset_button = QPushButton("Reset to defaults")
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.apply_button = QPushButton("Apply and start")
        self.apply_button.clicked.connect(self._on_apply_clicked)

        self.dirty_label = role_label("", "muted")
        set_property(self.apply_button, "variant", "primary")
        self.apply_button.setToolTip("Validate the setup and start a new run from the beginning.")
        self.validate_button.setToolTip("Check every value without starting anything.")
        self.reset_button.setToolTip("Put every control back to its default. Nothing is applied.")
        for spin in (
            self.warning_spin, self.abnormal_spin, self.latitude_spin,
            self.longitude_spin, self.tilt_spin, self.azimuth_spin, *self._module_spins.values(),
        ):
            spin.valueChanged.connect(self._update_dirty)
        self.profile_box.currentIndexChanged.connect(self._update_dirty)

        profile_group = QGroupBox("Input profile")
        layout = QVBoxLayout(profile_group)
        layout.addWidget(self.profile_box)
        layout.addWidget(self.load_csv_button)
        layout.addWidget(self.profile_info)

        module_group = QGroupBox("Module datasheet")
        layout = QVBoxLayout(module_group)
        layout.addWidget(self.module_label)
        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.setHorizontalSpacing(20)
        fields = [
            ("Isc", self.isc_spin, "A"), ("Voc", self.voc_spin, "V"),
            ("Impp", self.impp_spin, "A"), ("Vmpp", self.vmpp_spin, "V"),
            ("Ki", self.ki_spin, "%/°C"), ("Kv", self.kv_spin, "%/°C"),
            ("Ns", self.ns_spin, "cells"),
        ]
        for index, (label, spin, unit) in enumerate(fields):
            row, pair = divmod(index, 2)
            grid.addWidget(QLabel(label), row, 3 * pair)
            grid.addWidget(spin, row, 3 * pair + 1)
            grid.addWidget(role_label(unit, "muted"), row, 3 * pair + 2)
        grid.setColumnStretch(6, 1)
        layout.addLayout(grid)
        buttons = QHBoxLayout()
        buttons.addWidget(self.load_datasheet_button)
        buttons.addWidget(self.reset_module_button)
        layout.addLayout(buttons)

        site_group = QGroupBox("Site")
        site_group.setToolTip("Metadata only: the site does not change the physics.")
        form = site_form = QFormLayout(site_group)
        _roomy(form)
        form.addRow("Latitude", unit_row(self.latitude_spin, "°"))
        form.addRow("Longitude", unit_row(self.longitude_spin, "°"))
        form.addRow("Tilt", unit_row(self.tilt_spin, "°"))
        form.addRow("Azimuth", unit_row(self.azimuth_spin, "° (0 is north)"))

        threshold_group = QGroupBox("State thresholds")
        form = threshold_form = QFormLayout(threshold_group)
        _roomy(form)
        form.addRow("Warning limit", unit_row(self.warning_spin, "%"))
        form.addRow("Abnormal limit", unit_row(self.abnormal_spin, "%"))
        form.addRow(self.derive_button)

        _align_labels(site_form, threshold_form)

        summary_group = QGroupBox("Run summary")
        QVBoxLayout(summary_group).addWidget(self.summary_label)

        # A settings page: the sections in a list on the left, one section at a time on the right. Each page
        # is a column of readable width under its title, so nothing is packed.
        sections = (
            ("Profile", (profile_group, self.fetch_panel)),
            ("Site", (site_group,)),
            ("Module", (module_group,)),
            ("Limits", (threshold_group,)),
            ("Review", (summary_group,)),
        )
        self.section_list = QListWidget()
        self.section_list.setObjectName("sectionNav")
        self.section_list.setFixedWidth(NAV_WIDTH_PX)
        self.pages = QStackedWidget()
        row_height = self.section_list.fontMetrics().height() * 2 + 8  # Qt sizes list rows without the stylesheet's padding
        for title, groups in sections:
            item = QListWidgetItem(title)
            item.setSizeHint(QSize(NAV_WIDTH_PX, row_height))
            self.section_list.addItem(item)
            self.pages.addWidget(self._page(title, groups))
        self.section_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.section_list.setCurrentRow(0)
        # The page scrolls, so a short window shows the top of a page and the rest a scroll away.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.pages)
        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self.section_list)
        body.addWidget(scroll, 1)

        actions = QHBoxLayout()
        actions.addWidget(self.message_label, 1)
        actions.addWidget(self.dirty_label)
        actions.addSpacing(8)
        for button in (self.validate_button, self.reset_button, self.apply_button):
            actions.addWidget(button)

        root = QVBoxLayout(self)
        root.addLayout(body, 1)
        root.addLayout(actions)

    def _page(self, title: str, groups: tuple[QGroupBox, ...]) -> QWidget:
        """One section: its title, then its groups, in a column of readable width."""
        column = QWidget()
        column.setMaximumWidth(PAGE_MAX_WIDTH_PX)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(8, 12, 8, 16)
        layout.setSpacing(14)
        layout.addWidget(role_label(title, "title"))
        for group in groups:
            if len(groups) == 1:  # the page title already names a lone card
                group.setTitle("")
                group.setProperty("flat", "true")
            layout.addWidget(group)
        layout.addStretch(1)
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(column, 100)  # the column takes the room up to its maximum width
        outer.addStretch(1)
        return page
