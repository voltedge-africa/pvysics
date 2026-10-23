import numpy as np

from pvysics.gui.data_bus import DataBus
from pvysics.gui.main_window import MainWindow, bundled_result
from pvysics.gui.playback import SPEEDS
from pvysics.gui.process_view import PLACEHOLDER, STATE_COLOURS
from pvysics.run import RunResult, Sample, State, bundled_run_config

FASTEST = SPEEDS[-1]
GREEN, AMBER, RED = STATE_COLOURS[State.NORMAL], STATE_COLOURS[State.WARNING], STATE_COLOURS[State.ABNORMAL]
ORIGIN = np.datetime64("2025-01-15T12:00:00")


def sample_at(offset_s: float, state: State, deviation: float) -> Sample:
    return Sample(
        timestamp=ORIGIN + np.timedelta64(offset_s, "s"),
        true_irradiance=800.0,
        true_temperature=40.0,
        measured_irradiance=800.0,
        measured_temperature=40.0,
        measured_voltage=30.0,
        measured_current=7.5,
        power_measured=225.0,
        power_predicted=225.0 / (1.0 + deviation / 100.0),
        deviation_pct=deviation,
        state=state,
    )


def window_with(qtbot, run_result: RunResult | None = None, bus: DataBus | None = None) -> MainWindow:
    window = MainWindow(bus=bus, run_result=run_result)
    qtbot.addWidget(window)
    window.playback.set_speed(FASTEST)
    return window


def test_start_plays_pause_freezes_and_reset_returns_to_the_start(qtbot):
    window = window_with(qtbot)
    view = window.centralWidget()
    first_stamp = np.datetime_as_string(bundled_result().samples[0].timestamp, unit="m").replace("T", " ")

    view.start_button.click()
    window.playback.tick()
    shown_after_one_tick = view.time_label.text()
    view.pause_button.click()
    window.playback.tick()
    assert view.time_label.text() == shown_after_one_tick
    view.reset_button.click()

    assert view.time_label.text() == PLACEHOLDER
    assert view.banner.text() == "Ready"
    assert view.plant.value("G") == PLACEHOLDER
    view.start_button.click()
    window.playback.tick()
    assert view.time_label.text() == shown_after_one_tick
    assert shown_after_one_tick > first_stamp  # one tick at the fastest speed moves past 00:00


def test_start_and_pause_buttons_follow_the_run_state(qtbot):
    window = window_with(qtbot)
    view = window.centralWidget()
    assert view.start_button.isEnabled() and not view.pause_button.isEnabled()

    view.start_button.click()
    assert not view.start_button.isEnabled() and view.pause_button.isEnabled()

    view.pause_button.click()
    assert view.start_button.isEnabled() and not view.pause_button.isEnabled()


def test_speed_control_changes_the_rate_without_restarting_the_run(qtbot):
    window = window_with(qtbot)
    view = window.centralWidget()
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
    view = window.centralWidget()
    seen = []
    window.bus.sample.connect(seen.append)
    view.start_button.click()

    shown_values = []
    for _ in range(60):  # 16 simulated hours at the fastest speed, so daylight power is shown
        window.playback.tick()
        if seen:
            latest = seen[-1]
            assert view.plant.value("G") == f"{latest.measured_irradiance:.0f} W/m²"
            assert view.plant.value("T") == f"{latest.measured_temperature:.1f} °C"
            assert view.plant.value("V") == f"{latest.measured_voltage:.1f} V"
            assert view.plant.value("I") == f"{latest.measured_current:.1f} A"
            assert view.plant.value("P") == f"{latest.power_measured:.1f} W"
            assert view.twin.value("P_pred") == f"{latest.power_predicted:.1f} W"
            shown_values.append(view.plant.value("P"))
    assert len(set(shown_values)) > 1


def test_banner_and_gauge_follow_normal_warning_and_abnormal_samples(qtbot):
    run_result = RunResult(
        config=bundled_run_config(),
        samples=[
            sample_at(0, State.NORMAL, 1.0),
            sample_at(60, State.WARNING, -6.0),
            sample_at(120, State.ABNORMAL, 12.0),
        ],
    )
    window = window_with(qtbot, run_result=run_result)
    view = window.centralWidget()
    window.playback.set_speed(900.0)  # 30 simulated seconds per tick: one sample every two ticks
    view.start_button.click()

    window.playback.tick()
    assert view.banner.colour() == GREEN
    assert view.gauge.state is State.NORMAL

    window.playback.tick()
    assert view.banner.colour() == AMBER
    assert view.banner.text() == "Warning"
    assert view.gauge.state is State.WARNING
    assert view.gauge.reading_pct == 6.0

    window.playback.tick()
    window.playback.tick()
    assert view.banner.colour() == RED
    assert view.banner.text() == "Abnormal"
    assert view.gauge.reading_pct == 12.0


def test_the_window_shows_the_bus_it_was_given(qtbot):
    bus = DataBus()
    other_subscriber = []
    bus.sample.connect(other_subscriber.append)
    window = window_with(qtbot, bus=bus)

    window.centralWidget().start_button.click()
    window.playback.tick()

    assert window.bus is bus
    assert other_subscriber
    assert window.centralWidget().time_label.text() != PLACEHOLDER


def test_offscreen_smoke_plays_a_short_run_through_the_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    view = window.centralWidget()
    assert view.banner.text() == "Ready"

    window.playback.set_speed(FASTEST)
    view.start_button.click()
    for _ in range(5):
        window.playback.tick()
    window.grab()

    assert view.banner.text() in {"Normal", "Warning", "Abnormal"}
    assert view.plant.value("G") != PLACEHOLDER
    assert view.twin.value("P_pred") != PLACEHOLDER
    assert view.time_label.text() != PLACEHOLDER
    window.close()
    assert not window.isVisible()
