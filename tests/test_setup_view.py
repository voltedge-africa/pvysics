"""The Setup tab, driven offscreen. Nothing in it changes the run until Apply and start."""

import logging

import pytest
from PyQt6.QtWidgets import QFileDialog

from pvysics.gui.main_window import MainWindow
from pvysics.gui.playback import SPEEDS
from pvysics.gui.process_view import GAUGE_SCALE_FACTOR, PLACEHOLDER
from pvysics.run import RunConfig, Site, bundled_run_config
from pvysics.run_setup import derive_thresholds
from pvysics.single_diode import fit_parameters
from pvysics.gui.session import Session

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
    window = Session(config=config).open_hmi()
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


def test_module_fields_show_the_generic_datasheet(qtbot):
    setup = window_with(qtbot).setup_view

    assert setup.isc_spin.value() == pytest.approx(8.9)
    assert setup.voc_spin.value() == pytest.approx(37.8)
    assert setup.impp_spin.value() == pytest.approx(8.3)
    assert setup.vmpp_spin.value() == pytest.approx(30.1)
    assert setup.ki_spin.value() == pytest.approx(0.05)
    assert setup.kv_spin.value() == pytest.approx(-0.32)
    assert setup.ns_spin.value() == 60
    assert setup.datasheet_name == "Generic 60-cell 250 W"


def test_module_fields_show_a_loaded_file(qtbot, tmp_path):
    setup = window_with(qtbot).setup_view

    setup.load_datasheet(write(tmp_path, "my_module.json", JSON_MODULE))

    assert setup.datasheet_name == "my_module"
    assert setup.isc_spin.value() == pytest.approx(9.1)
    assert setup.voc_spin.value() == pytest.approx(36.5)
    assert setup.impp_spin.value() == pytest.approx(8.0)
    assert setup.vmpp_spin.value() == pytest.approx(29.5)
    assert setup.ki_spin.value() == pytest.approx(0.04)
    assert setup.kv_spin.value() == pytest.approx(-0.3)
    assert setup.ns_spin.value() == 60


def test_nothing_applies_until_apply_and_start(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    before = window.playback.config
    parameters = window.model_view.parameters

    setup.isc_spin.setValue(9.4)
    setup.impp_spin.setValue(8.5)

    assert window.playback.config is before
    assert window.model_view.parameters is parameters
    assert setup.read_config().datasheet.isc_a == pytest.approx(9.4)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda s: s.isc_spin.setValue(0.0), "Isc must be above zero"),
        (lambda s: s.voc_spin.setValue(0.0), "Voc must be above zero"),
        (lambda s: s.impp_spin.setValue(0.0), "Impp must be above zero"),
        (lambda s: s.vmpp_spin.setValue(0.0), "Vmpp must be above zero"),
        (lambda s: s.ns_spin.setValue(0), "Ns must be a positive whole number"),
        (lambda s: s.vmpp_spin.setValue(40.0), "Vmpp must be below Voc"),
        (lambda s: s.impp_spin.setValue(9.5), "Impp must be below Isc"),
        (lambda s: s.ki_spin.setValue(6.0), "Ki must be within 5 %/C"),
        (lambda s: s.kv_spin.setValue(-6.0), "Kv must be within 5 %/C"),
        (lambda s: s.kv_spin.setValue(0.3), "Kv must be zero or negative"),
        (
            lambda s: (s.vmpp_spin.setValue(11.3), s.impp_spin.setValue(8.8)),
            "No diode model can be fitted",
        ),
    ],
)
def test_each_invalid_module_value_gives_its_message_is_logged_and_keeps_the_module(
    qtbot, caplog, change, message
):
    window = window_with(qtbot)
    setup = window.setup_view
    before = window.playback.config
    change(setup)

    with caplog.at_level(logging.WARNING, logger="pvysics"):
        assert setup.validate()
        assert message in setup.message
        setup.apply()

    assert window.playback.config is before
    assert window.playback.config.datasheet.name == "Generic 60-cell 250 W"
    assert any(record.levelno == logging.WARNING and message in record.getMessage() for record in caplog.records)


def test_validate_reports_a_valid_edited_module_without_applying(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    before = window.playback.config
    setup.isc_spin.setValue(9.4)

    assert setup.validate() == []
    assert window.playback.config is before


def test_derive_refuses_while_the_module_has_a_problem(qtbot):
    setup = window_with(qtbot).setup_view
    setup.ns_spin.setValue(0)

    setup.derive_button.click()

    assert "Cannot derive" in setup.message


def test_reset_to_generic_module_restores_the_values_and_applies_nothing(qtbot, tmp_path):
    window = window_with(qtbot)
    setup = window.setup_view
    before = window.playback.config
    setup.load_datasheet(write(tmp_path, "my_module.json", JSON_MODULE))
    setup.isc_spin.setValue(9.5)

    setup.reset_module_button.click()

    assert setup.datasheet_name == "Generic 60-cell 250 W"
    assert setup.isc_spin.value() == pytest.approx(8.9)
    assert setup.voc_spin.value() == pytest.approx(37.8)
    assert setup.ns_spin.value() == 60
    assert window.playback.config is before


def test_edited_module_is_named_custom_and_shown_in_the_run_summary(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    setup.isc_spin.setValue(9.3)
    setup.ns_spin.setValue(72)

    setup.apply()

    applied = window.playback.config.datasheet
    assert applied.name == "Custom module"
    assert applied.isc_a == pytest.approx(9.3)
    assert applied.ns == 72
    assert "Custom module" in setup.summary_label.text()
    assert "Isc 9.3 A" in setup.summary_label.text()
    assert "Ns 72" in setup.summary_label.text()


def test_apply_and_start_changes_the_model_tab_parameters(qtbot):
    window = window_with(qtbot)
    setup = window.setup_view
    iph_before = window.model_view.parameter_panel.value("iph")
    setup.isc_spin.setValue(9.4)
    setup.impp_spin.setValue(8.5)

    setup.apply_button.click()

    applied = window.playback.config.datasheet
    assert window.model_view.datasheet_panel.value("isc") == "9.40 A"
    assert window.model_view.datasheet_panel.value("impp") == "8.50 A"
    assert window.model_view.parameters == fit_parameters(applied)
    assert window.model_view.parameter_panel.value("iph") != iph_before
