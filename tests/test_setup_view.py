"""The Setup tab, driven offscreen. Nothing in it changes the run until Apply and start."""

import pytest
from PyQt6.QtWidgets import QFileDialog

from pvysics.gui.main_window import MainWindow
from pvysics.gui.playback import SPEEDS
from pvysics.gui.process_view import GAUGE_SCALE_FACTOR, PLACEHOLDER
from pvysics.run import RunConfig, Site, bundled_run_config
from pvysics.run_setup import derive_thresholds
from pvysics.single_diode import fit_parameters

FASTEST = SPEEDS[-1]
HOURLY_CSV = (
    "time,ghi,temp_air\n"
    "2025-06-01T08:00:00,250.5,18.0\n"
    "2025-06-01T09:00:00,400.0,19.5\n"
    "2025-06-01T10:00:00,520.0,21.0\n"
)
JSON_MODULE = (
    '{"Isc": 9.1, "Voc": 36.5, "Impp": 8.0, "Vmpp": 29.5, "Ki": 0.04, "Kv": -0.3, "Ns": 60}'
)


def window_with(qtbot, config: RunConfig | None = None) -> MainWindow:
    window = MainWindow(config=config)
    qtbot.addWidget(window)
    window.playback.set_speed(FASTEST)
    return window


def write(tmp_path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_bundled_days_appear_as_presets(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view

    names = [setup.profile_box.itemText(index) for index in range(setup.profile_box.count())]

    assert names == ["Bundled 2025-01-15", "Bundled 2025-01-16", "Bundled 2025-01-17"]


def test_controls_start_with_the_active_run(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view

    assert setup.profile_name == "Bundled 2025-01-15"
    assert setup.datasheet_name == bundled_run_config().datasheet.name
    assert setup.rs_spin.value() == pytest.approx(3.0)
    assert setup.warning_spin.value() == pytest.approx(5.0)
    assert setup.abnormal_spin.value() == pytest.approx(10.0)
    assert setup.latitude_spin.value() == pytest.approx(-29.85)
    assert setup.longitude_spin.value() == pytest.approx(31.00)
    assert setup.tilt_spin.value() == pytest.approx(26.0)
    assert setup.azimuth_spin.value() == pytest.approx(0.0)


def test_valid_csv_loads_once_accepted_and_only_applies_at_apply(qtbot, tmp_path):
    window = window_with(qtbot)
    setup = window.setup_view
    before = window.playback.config
    setup.load_csv(write(tmp_path, "site.csv", HOURLY_CSV))
    dialog = setup.csv_dialog

    assert dialog.use_button.isEnabled()
    assert "Passed" in dialog.checks_label.text()
    dialog.accept()

    assert setup.profile_name == "site.csv"
    assert window.playback.config is before

    setup.apply()

    assert window.playback.config.profile.name == "site.csv"


def test_load_csv_button_opens_the_column_mapping(qtbot, tmp_path, monkeypatch):
    window = window_with(qtbot)
    setup = window.setup_view
    path = write(tmp_path, "site.csv", HOURLY_CSV)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (path, ""))

    setup.load_csv_button.click()

    assert setup.csv_dialog is not None
    assert setup.csv_dialog.timestamp_box.currentData() == "time"
    assert setup.csv_dialog.temperature_box.currentData() == "temp_air"
    setup.csv_dialog.reject()


def test_nasa_layout_is_offered_as_a_timestamp_and_passes(qtbot, tmp_path):
    window = window_with(qtbot)
    setup = window.setup_view
    text = (
        "YEAR,MO,DY,HR,ALLSKY_SFC_SW_DWN,T2M\n"
        "2025,1,15,0,0.0,26.1\n"
        "2025,1,15,1,0.0,25.9\n"
    )

    setup.load_csv(write(tmp_path, "nasa.csv", text))

    assert setup.csv_dialog.timestamp_box.currentData() == "YEAR,MO,DY,HR"
    assert setup.csv_dialog.use_button.isEnabled()
    setup.csv_dialog.reject()


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("time,ghi\n2025-06-01T08:00:00,250.5\n2025-06-01T09:00:00,400.0\n", "temperature"),
        (HOURLY_CSV.replace("400.0", "n/a"), "not a number"),
        (
            "time,ghi,temp_air\n2025-06-01T10:00:00,1,1\n2025-06-01T09:00:00,1,1\n",
            "does not increase",
        ),
        (HOURLY_CSV.replace("400.0", "-5.0"), "negative"),
    ],
)
def test_rejected_csv_shows_a_specific_message_and_keeps_the_previous_profile(
    qtbot, tmp_path, text, reason
):
    window = window_with(qtbot)
    setup = window.setup_view
    setup.load_csv(write(tmp_path, "bad.csv", text))
    dialog = setup.csv_dialog

    assert not dialog.use_button.isEnabled()
    assert reason in dialog.checks_label.text()
    dialog.accept()  # the Use profile button is disabled, so accepting does nothing

    assert setup.profile_name == "Bundled 2025-01-15"
    setup.apply()
    assert window.playback.config.profile.name == "Bundled 2025-01-15"
    dialog.reject()


def test_malformed_datasheet_is_rejected_and_a_good_one_loads(qtbot, tmp_path):
    window = window_with(qtbot)
    setup = window.setup_view
    generic = setup.datasheet_name

    setup.load_datasheet(write(tmp_path, "broken.json", '{"Isc": 9.1}'))

    assert "Voc" in setup.message
    assert setup.datasheet_name == generic

    setup.load_datasheet(write(tmp_path, "my_module.json", JSON_MODULE))

    assert setup.datasheet_name == "my_module"


def test_changes_to_mismatch_noise_seed_and_thresholds_wait_for_apply(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    before = window.playback.config

    setup.rs_spin.setValue(10.0)
    setup.irradiance_noise_spin.setValue(1.5)
    setup.seed_spin.setValue(5)
    setup.warning_spin.setValue(2.0)
    setup.abnormal_spin.setValue(4.0)

    assert window.playback.config is before

    setup.apply()

    applied = window.playback.config
    assert applied.mismatch.series_resistance_pct == pytest.approx(10.0)
    assert applied.sensors.irradiance_noise_pct == pytest.approx(1.5)
    assert applied.seed == 5
    assert (applied.thresholds.warning_pct, applied.thresholds.abnormal_pct) == (2.0, 4.0)
    assert applied == setup.read_config()


def test_invalid_thresholds_are_reported_and_not_applied(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    before = window.playback.config
    setup.warning_spin.setValue(12.0)  # above the abnormal limit of 10 %

    assert setup.validate()
    assert "abnormal" in setup.message.lower()
    setup.apply()

    assert window.playback.config is before
    assert not window.playback.is_running


def test_validate_reports_a_valid_setup_without_starting(qtbot):
    window = window_with(qtbot)

    assert window.setup_view.validate() == []
    assert "valid" in window.setup_view.message
    assert not window.playback.is_running


def test_derive_thresholds_fills_the_limits_which_stay_editable(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    expected = derive_thresholds(setup.read_config())

    setup.derive_button.click()

    assert setup.warning_spin.value() == pytest.approx(expected.warning_pct, abs=0.005)
    assert setup.abnormal_spin.value() == pytest.approx(expected.abnormal_pct, abs=0.005)
    setup.warning_spin.setValue(1.5)
    assert setup.warning_spin.value() == pytest.approx(1.5)


def test_site_is_saved_and_shown_in_the_run_summary(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    setup.latitude_spin.setValue(-26.2)
    setup.longitude_spin.setValue(28.04)
    setup.tilt_spin.setValue(10.0)
    setup.azimuth_spin.setValue(180.0)

    setup.apply()

    assert window.playback.config.site == Site(-26.2, 28.04, 10.0, 180.0)
    assert "latitude -26.20" in setup.summary_label.text()
    assert "(metadata only)" in setup.summary_label.text()


def test_reset_to_defaults_restores_the_controls_and_applies_nothing(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    before = window.playback.config
    setup.rs_spin.setValue(10.0)
    setup.seed_spin.setValue(9)
    setup.warning_spin.setValue(2.0)
    setup.profile_box.setCurrentIndex(1)  # Bundled 2025-01-16

    setup.reset_to_defaults()

    assert setup.profile_name == "Bundled 2025-01-15"
    assert setup.rs_spin.value() == pytest.approx(3.0)
    assert setup.seed_spin.value() == 0
    assert setup.warning_spin.value() == pytest.approx(5.0)
    assert setup.abnormal_spin.value() == pytest.approx(10.0)
    assert window.playback.config is before


def test_apply_and_start_runs_the_changed_setup(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    window.playback.start()
    window.playback.tick()
    assert window.history.sample_count > 0
    setup.rs_spin.setValue(6.0)
    setup.warning_spin.setValue(2.0)
    setup.abnormal_spin.setValue(4.0)

    setup.apply_button.click()

    assert window.playback.is_running
    assert window.centralWidget().currentWidget() is window.process_view
    assert window.history.sample_count == 0  # the history belongs to the new run
    window.playback.tick()
    assert window.history.sample_count > 0
    assert window.process_view.time_label.text() != PLACEHOLDER
    assert window.process_view.gauge.scale_pct == pytest.approx(GAUGE_SCALE_FACTOR * 4.0)


def test_dashboard_takes_the_applied_limits(qtbot):
    window = window_with(qtbot)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    setup = window.setup_view
    setup.warning_spin.setValue(2.0)
    setup.abnormal_spin.setValue(4.0)

    setup.apply()

    assert dashboard.thresholds.warning_pct == pytest.approx(2.0)
    assert dashboard.thresholds.abnormal_pct == pytest.approx(4.0)


def test_model_view_refits_the_applied_module(qtbot, tmp_path):
    window = window_with(qtbot)
    setup = window.setup_view
    setup.load_datasheet(write(tmp_path, "my_module.json", JSON_MODULE))

    setup.apply()

    applied = window.playback.config.datasheet
    assert applied.name == "my_module"
    assert window.model_view.parameters == fit_parameters(applied)
