"""The Sensors window and its Setup tab, offscreen."""

import pytest
from dataclasses import replace

from pvysics.gui.process_view import format_readings
from pvysics.gui.sensor_setup import HTTP, MQTT, SERIAL, SIMULATED
from pvysics.gui.sensors import HARDWARE_NOT_CONNECTED, SensorsWindow
from pvysics.gui.session import Session
from pvysics.profile import Profile
from pvysics.run import bundled_run_config

FASTEST = 28800.0


def midday_config():
    config = bundled_run_config(seed=1)
    profile = config.profile
    cut = Profile(
        timestamps=profile.timestamps[10:15],
        irradiance=profile.irradiance[10:15],
        temperature=profile.temperature[10:15],
    )
    return replace(config, profile=cut)


@pytest.fixture
def session(qtbot):
    session = Session(config=midday_config())
    session.playback.set_speed(FASTEST)
    yield session
    session.close()


def sensors_window(qtbot, session) -> SensorsWindow:
    window = session.open_sensors()
    qtbot.addWidget(window)
    return window


def run_a_few_ticks(session, window, ticks=3):
    session.playback.start()
    for _ in range(ticks):
        session.playback.tick()
    window.refresh()


def test_the_sensors_window_shows_the_plants_readings_and_the_hmi_and_dashboard_do_not(qtbot, session):
    window = sensors_window(qtbot, session)
    hmi, dashboard = session.open_hmi(), session.open_dashboard()
    qtbot.addWidget(hmi)
    qtbot.addWidget(dashboard)
    run_a_few_ticks(session, window)

    readings = format_readings(session.history.latest)
    for key in ("G", "T", "V", "I", "P"):
        assert window.strip.value(key) == readings[key]
        for other in (hmi.process_view.strip, dashboard.strip):
            with pytest.raises(KeyError):
                other.value(key)


def test_each_sensor_channel_has_a_chart_with_the_whole_run_and_irradiance_shares_a_pane_with_temperature(qtbot, session):
    window = sensors_window(qtbot, session)
    run_a_few_ticks(session, window)
    count = session.history.sample_count

    for curve, column in window._curves.items():
        assert len(curve.getData()[1]) == count
    assert window.charts.tabifiedDockWidgets(window.docks["irradiance"]) == [window.docks["temperature"]]


def test_a_reset_clears_the_sensor_figures_and_charts(qtbot, session):
    window = sensors_window(qtbot, session)
    run_a_few_ticks(session, window)

    session.playback.reset()
    window.refresh()

    assert window.strip.value("G") == "-"
    assert all(len(curve.getData()[1] or []) == 0 for curve in window._curves)


def test_the_header_says_the_source_is_simulated_and_no_hardware_is_connected(qtbot, session):
    window = sensors_window(qtbot, session)

    assert window.source_label.text() == "Simulated plant"
    assert window.hardware_label.text() == HARDWARE_NOT_CONNECTED


def test_the_window_has_a_live_tab_and_a_setup_tab(qtbot, session):
    window = sensors_window(qtbot, session)

    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == ["Live", "Setup"]


def test_the_setup_tab_starts_with_the_runs_plant(qtbot, session):
    setup = sensors_window(qtbot, session).setup_view
    config = session.config

    assert setup.rs_spin.value() == pytest.approx(config.mismatch.series_resistance_pct)
    assert setup.irradiance_noise_spin.value() == pytest.approx(config.sensors.irradiance_noise_pct)
    assert setup.seed_spin.value() == config.seed
    assert not setup.has_unapplied_changes


def test_changes_to_the_plant_wait_for_apply_then_start_a_new_run(qtbot, session):
    setup = sensors_window(qtbot, session).setup_view
    before = session.config
    setup.rs_spin.setValue(10.0)
    setup.irradiance_noise_spin.setValue(1.5)
    setup.seed_spin.setValue(5)

    assert setup.has_unapplied_changes
    assert session.config is before
    setup.apply()

    applied = session.config
    assert applied.mismatch.series_resistance_pct == pytest.approx(10.0)
    assert applied.sensors.irradiance_noise_pct == pytest.approx(1.5)
    assert applied.seed == 5
    assert applied.profile is before.profile and applied.thresholds == before.thresholds
    assert session.playback.is_running
    assert not setup.has_unapplied_changes


def test_a_plant_the_checks_reject_is_reported_and_not_applied(qtbot, session, monkeypatch):
    setup = sensors_window(qtbot, session).setup_view
    before = session.config
    monkeypatch.setattr("pvysics.gui.sensor_setup.validate_config", lambda config: ["The Rs offset must be above -100 %."])

    setup.apply()

    assert setup.message == "Not applied. The Rs offset must be above -100 %."
    assert session.config is before


def test_reset_restores_the_default_plant_and_applies_nothing(qtbot, session):
    setup = sensors_window(qtbot, session).setup_view
    before = session.config
    setup.rs_spin.setValue(10.0)

    setup.reset_plant()

    assert setup.rs_spin.value() == pytest.approx(3.0)
    assert session.config is before


def test_the_hmi_setup_carries_a_plant_applied_in_the_sensors_window(qtbot, session):
    hmi = session.open_hmi()
    qtbot.addWidget(hmi)
    setup = sensors_window(qtbot, session).setup_view
    setup.rs_spin.setValue(8.0)

    setup.apply()

    assert hmi.setup_view.read_config().mismatch.series_resistance_pct == pytest.approx(8.0)
    assert not hmi.setup_view.has_unapplied_changes  # a plant change made elsewhere is not an unapplied HMI edit


def test_the_sources_are_the_simulated_plant_and_three_kinds_of_hardware_feed(qtbot, session):
    setup = sensors_window(qtbot, session).setup_view

    assert [setup.source_box.itemText(i) for i in range(setup.source_box.count())] == [SIMULATED, SERIAL, MQTT, HTTP]
    assert setup.source == SIMULATED
    assert not setup.channels_group.isVisibleTo(setup)


def test_choosing_hardware_shows_its_connection_settings_and_the_channel_names(qtbot, session):
    setup = sensors_window(qtbot, session).setup_view

    setup.source_box.setCurrentIndex(setup.source_box.findText(MQTT))

    assert setup.connection_pages.currentIndex() == 2
    assert setup.channels_group.isVisibleTo(setup)
    assert list(setup.channel_edits) == ["Irradiance", "Module temperature", "Voltage", "Current"]


@pytest.mark.parametrize(
    ("source", "fill", "needle"),
    [
        (SERIAL, lambda s: s.port_edit.setText(""), "serial port"),
        (MQTT, lambda s: s.host_edit.setText(""), "host name"),
        (MQTT, lambda s: s.topic_edit.setText(""), "topic"),
        (HTTP, lambda s: s.url_edit.setText("192.168.1.20"), "must start with"),
    ],
)
def test_missing_connection_settings_are_named_in_plain_words(qtbot, session, source, fill, needle):
    setup = sensors_window(qtbot, session).setup_view
    setup.source_box.setCurrentIndex(setup.source_box.findText(source))
    if source == SERIAL:
        setup.port_edit.setText("/dev/ttyUSB0")
    fill(setup)

    setup.connect_source()

    assert needle in " ".join(setup.connection_problems())
    assert setup.message.startswith("Not connected")


def test_two_channels_cannot_share_a_field_name(qtbot, session):
    setup = sensors_window(qtbot, session).setup_view
    setup.source_box.setCurrentIndex(setup.source_box.findText(SERIAL))
    setup.port_edit.setText("COM3")
    setup.channel_edits["Voltage"].setText("current")

    assert "own field name" in " ".join(setup.connection_problems())


def test_connecting_a_hardware_feed_says_plainly_that_there_is_no_driver_yet(qtbot, session):
    window = sensors_window(qtbot, session)
    setup = window.setup_view
    setup.source_box.setCurrentIndex(setup.source_box.findText(SERIAL))
    setup.port_edit.setText("/dev/ttyUSB0")

    setup.connect_source()

    assert "No hardware driver" in setup.message
    assert "not available yet" in window.hardware_label.text()
    assert window.source_label.text() == "Simulated plant"  # nothing pretends to be connected


def test_using_the_simulated_plant_restores_the_header(qtbot, session):
    window = sensors_window(qtbot, session)
    setup = window.setup_view
    setup.source_box.setCurrentIndex(setup.source_box.findText(SERIAL))
    setup.port_edit.setText("COM3")
    setup.connect_source()
    setup.source_box.setCurrentIndex(0)

    setup.connect_source()

    assert window.hardware_label.text() == HARDWARE_NOT_CONNECTED


def test_the_window_menus_reach_the_other_windows_and_the_log_pop_up(qtbot, session):
    window = sensors_window(qtbot, session)

    assert window.open_hmi_action.text() == "Open HMI"
    assert window.open_dashboard_action.text() == "Open Dashboard"
    assert window.log_pane.isFloating() and not window.log_pane.isVisible()
    assert session.hmi is None
    window.open_hmi_action.trigger()
    assert session.hmi is not None


def test_measured_power_has_a_chart_beside_voltage_and_current(qtbot, session):
    window = sensors_window(qtbot, session)
    run_a_few_ticks(session, window)

    power = window._curves_by_column["power_measured"]
    assert len(power.getData()[1]) == session.history.sample_count
    assert power.getData()[1][-1] == pytest.approx(session.history.latest.power_measured)
    assert "power_measured" in window.docks


def test_alarms_are_recorded_and_logged_without_a_dashboard_and_listed_in_the_dashboard(qtbot, session):
    from pvysics.faults import FaultKind

    hmi = session.open_hmi()
    qtbot.addWidget(hmi)
    hmi.process_view.start_button.click()
    hmi.process_view.fault_buttons[FaultKind.PARTIAL_SHADING].click()
    session.playback.tick()

    assert session.alarms.log.alarms  # recorded with no Dashboard open
    dashboard = session.open_dashboard()
    qtbot.addWidget(dashboard)
    assert dashboard.alarm_panel.list_widget.count() == len(session.alarms.log.alarms)
    assert "Alarms" in [dashboard.centralWidget().tabText(i) for i in range(dashboard.centralWidget().count())]
