from dataclasses import replace

import numpy as np

from pvysics.faults import Fault, FaultKind
from pvysics.gui.main_window import MainWindow
from pvysics.gui.playback import SPEEDS
from pvysics.gui.process_view import PLACEHOLDER, STATE_COLOURS, format_number
from pvysics.profile import Profile
from pvysics.run import RunConfig, State, bundled_run_config
from pvysics.gui.session import Session

FASTEST = SPEEDS[-1]
GREEN = STATE_COLOURS[State.NORMAL]
AMBER = STATE_COLOURS[State.WARNING]
RED = STATE_COLOURS[State.ABNORMAL]


def midday_config() -> RunConfig:
    """The bundled day cut to 10:00 to 14:00, so a few ticks at the fastest speed cover it."""
    config = bundled_run_config(seed=1)
    profile = config.profile
    cut = Profile(
        timestamps=profile.timestamps[10:15],
        irradiance=profile.irradiance[10:15],
        temperature=profile.temperature[10:15],
    )
    return replace(config, profile=cut)


def window_with(qtbot, config: RunConfig | None = None) -> MainWindow:
    window = Session(config=config).open_hmi()
    qtbot.addWidget(window)
    window.playback.set_speed(FASTEST)
    return window


def test_start_plays_pause_freezes_and_reset_returns_to_the_start(qtbot):
    window = window_with(qtbot)
    view = window.process_view
    first = bundled_run_config().profile.timestamps[0]
    first_stamp = np.datetime_as_string(first, unit="m").replace("T", " ")

    view.start_button.click()
    window.playback.tick()
    shown_after_one_tick = view.time_label.text()
    view.pause_button.click()
    window.playback.tick()
    assert view.time_label.text() == shown_after_one_tick
    view.reset_button.click()

    assert view.time_label.text() == PLACEHOLDER
    assert view.banner.text() == "Ready"
    assert view.strip.value("G") == PLACEHOLDER
    view.start_button.click()
    window.playback.tick()
    assert view.time_label.text() == shown_after_one_tick
    assert shown_after_one_tick > first_stamp  # one tick at the fastest speed moves past 00:00


def test_start_and_pause_buttons_follow_the_run_state(qtbot):
    window = window_with(qtbot)
    view = window.process_view
    assert view.start_button.isEnabled() and not view.pause_button.isEnabled()

    view.start_button.click()
    assert not view.start_button.isEnabled() and view.pause_button.isEnabled()

    view.pause_button.click()
    assert view.start_button.isEnabled() and not view.pause_button.isEnabled()


def test_speed_control_changes_the_rate_without_restarting_the_run(qtbot):
    window = window_with(qtbot)
    view = window.process_view
    window.playback.set_speed(SPEEDS[0])
    resets = []
    window.bus.run_reset.connect(lambda: resets.append(True))
    view.start_button.click()
    window.playback.tick()
    stamp_before = view.time_label.text()

    view.speed_box.setCurrentIndex(len(SPEEDS) - 1)
    window.playback.tick()

    assert window.playback.speed == FASTEST
    assert window.playback.is_running
    assert resets == []
    assert view.time_label.text() > stamp_before


def test_plant_and_twin_readings_update_on_every_sample(qtbot):
    window = window_with(qtbot)
    view = window.process_view
    seen = []
    window.bus.sample.connect(seen.append)
    view.start_button.click()

    shown_values = []
    for _ in range(60):  # 16 simulated hours at the fastest speed, so daylight power is shown
        window.playback.tick()
        if seen:
            latest = seen[-1]
            assert view.strip.value("G") == f"{format_number(latest.measured_irradiance, 0)} W/m²"
            assert view.strip.value("T") == f"{format_number(latest.measured_temperature, 1)} °C"
            assert view.strip.value("V") == f"{format_number(latest.measured_voltage, 1)} V"
            assert view.strip.value("I") == f"{format_number(latest.measured_current, 1)} A"
            assert view.strip.value("P") == f"{format_number(latest.power_measured, 1)} W"
            assert view.strip.value("P_pred") == f"{format_number(latest.power_predicted, 1)} W"
            shown_values.append(view.strip.value("P"))
    assert len(set(shown_values)) > 1


def test_banner_and_gauge_follow_normal_warning_and_abnormal_faults(qtbot):
    window = window_with(qtbot, config=midday_config())
    view = window.process_view
    view.start_button.click()

    window.playback.tick()
    assert view.banner.colour() == GREEN
    assert view.strip.gauge_state is State.NORMAL

    window.playback.inject(Fault(FaultKind.SENSOR_DRIFT, 0.08))  # a deviation between the limits
    window.playback.tick()
    assert view.banner.colour() == AMBER
    assert view.banner.text() == "Warning"
    assert view.strip.gauge_state is State.WARNING

    view.fault_buttons[FaultKind.SENSOR_DRIFT].click()  # the default drift, past the abnormal limit
    window.playback.tick()
    assert view.banner.colour() == RED
    assert view.banner.text() == "Abnormal"
    assert view.strip.gauge_state is State.ABNORMAL


def test_fault_button_injects_and_clear_all_returns_the_banner_to_normal(qtbot):
    window = window_with(qtbot, config=midday_config())
    view = window.process_view
    view.start_button.click()
    window.playback.tick()

    view.fault_buttons[FaultKind.PARTIAL_SHADING].click()
    window.playback.tick()
    assert view.banner.text() == "Abnormal"

    view.clear_faults_button.click()
    window.playback.tick()
    assert view.banner.text() == "Normal"


def test_alarm_list_shows_time_severity_and_cause_and_can_be_acknowledged(qtbot):
    window = window_with(qtbot, config=midday_config())
    view = window.process_view
    panel = view.alarm_panel
    view.start_button.click()
    window.playback.tick()
    assert panel.list_widget.count() == 0
    assert panel.summary_label.text() == "No new alarms"

    view.fault_buttons[FaultKind.PARTIAL_SHADING].click()
    window.playback.tick()

    assert panel.list_widget.count() == 1
    item = panel.list_widget.item(0)
    assert "ABNORMAL" in item.text()
    assert "partial shading" in item.text()
    assert item.font().bold()
    assert panel.summary_label.text() == "1 new"
    assert panel.acknowledge_button.isEnabled()

    panel.acknowledge_button.click()

    assert "(seen)" in panel.list_widget.item(0).text()
    assert not panel.list_widget.item(0).font().bold()
    assert panel.summary_label.text() == "No new alarms"
    assert not panel.acknowledge_button.isEnabled()


def test_injected_faults_and_state_changes_are_emitted_on_the_bus(qtbot):
    window = window_with(qtbot, config=midday_config())
    events = []
    window.bus.event.connect(events.append)
    window.process_view.start_button.click()
    window.playback.tick()

    window.process_view.fault_buttons[FaultKind.SOILING].click()
    window.playback.tick()

    details = [(event.kind, event.detail) for event in events]
    assert ("fault", "none -> soiling") in details
    assert ("state", "Normal -> Abnormal") in details


def test_reset_clears_the_alarm_list(qtbot):
    window = window_with(qtbot, config=midday_config())
    view = window.process_view
    view.start_button.click()
    view.fault_buttons[FaultKind.PARTIAL_SHADING].click()
    window.playback.tick()
    assert view.alarm_panel.list_widget.count() == 1

    view.reset_button.click()

    assert view.alarm_panel.list_widget.count() == 0


def test_the_window_shows_the_bus_of_its_session(qtbot):
    session = Session()
    other_subscriber = []
    session.bus.sample.connect(other_subscriber.append)
    window = session.open_hmi()
    qtbot.addWidget(window)

    window.process_view.start_button.click()
    window.playback.tick()

    assert window.bus is session.bus
    assert other_subscriber
    assert window.process_view.time_label.text() != PLACEHOLDER


def test_offscreen_smoke_plays_a_short_run_through_the_window(qtbot):
    window = Session().open_hmi()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    view = window.process_view
    assert view.banner.text() == "Ready"

    window.playback.set_speed(FASTEST)
    view.start_button.click()
    for _ in range(5):
        window.playback.tick()
    view.fault_buttons[FaultKind.SENSOR_DRIFT].click()
    for _ in range(5):
        window.playback.tick()
    window.grab()

    assert view.banner.text() in {"Normal", "Warning", "Abnormal"}
    assert view.strip.value("G") != PLACEHOLDER
    assert view.strip.value("P_pred") != PLACEHOLDER
    assert view.time_label.text() != PLACEHOLDER
    window.close()
    assert not window.isVisible()


def test_an_empty_trend_shows_a_day_and_follows_the_data_from_the_first_sample(qtbot):
    window = Session(config=midday_config()).open_hmi()
    qtbot.addWidget(window)
    trend = window.process_view.trend
    (x_low, x_high), (y_low, y_high) = trend.plot.viewRange()

    assert (x_low, x_high) == (0, 24)
    assert y_low == 0 and y_high > 0
    window.process_view.start_button.click()
    window.playback.tick()
    trend.flush()
    assert trend.plot.plotItem.vb.state["autoRange"][0] is not False
