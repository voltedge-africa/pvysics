from dataclasses import replace

import numpy as np
import pyqtgraph as pg
import pytest
from PyQt6.QtWidgets import QAbstractButton, QAbstractSpinBox, QComboBox, QLineEdit, QSlider

from pvysics.faults import FaultKind, default_fault
from pvysics.gui.dashboard import Dashboard
from pvysics.gui.main_window import MainWindow
from pvysics.gui.session import Session
from pvysics.gui.playback import SPEEDS
from pvysics.gui.process_view import GAUGE_SCALE_FACTOR, PLACEHOLDER, STATE_COLOURS, format_readings
from pvysics.profile import Profile
from pvysics.run import RunConfig, State, Thresholds, bundled_run_config

FASTEST = SPEEDS[-1]
CURVE_COUNT = 5  # measured, predicted, deviation, irradiance, temperature


def midday_config(thresholds: Thresholds | None = None) -> RunConfig:
    """The bundled day cut to 10:00 to 14:00, so a few ticks at the fastest speed cover it."""
    config = bundled_run_config(seed=1)
    profile = config.profile
    cut = Profile(
        timestamps=profile.timestamps[10:15],
        irradiance=profile.irradiance[10:15],
        temperature=profile.temperature[10:15],
    )
    config = replace(config, profile=cut)
    return config if thresholds is None else replace(config, thresholds=thresholds)


def window_with(qtbot, config: RunConfig | None = None) -> MainWindow:
    window = Session(config=config).open_hmi()
    qtbot.addWidget(window)
    window.playback.set_speed(FASTEST)
    return window


def plotted_deviation(dashboard: Dashboard) -> np.ndarray:
    _x, y = dashboard._deviation.getData()
    return np.array([] if y is None else y)


def event_texts(dashboard: Dashboard) -> list[str]:
    return [dashboard.event_list.item(row).text() for row in range(dashboard.event_list.count())]


@pytest.fixture
def plot_calls(monkeypatch) -> list:
    """Records every curve update the Dashboard makes."""
    calls = []
    original = pg.PlotDataItem.setData

    def recording(self, *args, **kwargs):
        calls.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pg.PlotDataItem, "setData", recording)
    return calls


def test_dashboard_and_hmi_show_the_same_run(qtbot):
    window = window_with(qtbot, config=midday_config())
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    window.process_view.start_button.click()
    for _ in range(3):
        window.playback.tick()
    dashboard.refresh()

    latest = window.history.latest
    readings = format_readings(latest)
    assert dashboard.tiles["p_measured"].text() == readings["P"]
    assert dashboard.tiles["p_predicted"].text() == readings["P_pred"]
    assert dashboard.tiles["deviation"].text() == f"{latest.deviation_pct:+.1f} %"
    assert dashboard.tiles["state"].text() == latest.state.value
    assert dashboard.tiles["energy"].text() == f"{window.history.energy_wh:.1f} Wh"
    assert window.process_view.plant.value("P") == readings["P"]
    assert window.history.energy_wh > 0.0
    assert len(plotted_deviation(dashboard)) == window.history.sample_count


def test_overview_has_no_controls_that_change_the_run(qtbot):
    window = window_with(qtbot, config=midday_config())
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)

    controls = dashboard.overview.findChildren(
        (QAbstractButton, QComboBox, QAbstractSpinBox, QLineEdit, QSlider)
    )

    assert controls == []  # the only controls are on the Validation tab, and they do not touch the run


def test_deviation_chart_draws_warning_and_abnormal_bands_at_the_current_thresholds(qtbot):
    thresholds = Thresholds(warning_pct=2.0, abnormal_pct=4.0)
    window = window_with(qtbot, config=midday_config(thresholds))
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)

    regions = {
        item.getRegion()
        for item in dashboard.deviation_plot.getPlotItem().items
        if isinstance(item, pg.LinearRegionItem)
    }
    scale = GAUGE_SCALE_FACTOR * 4.0

    assert regions == {
        (-2.0, 2.0),  # Normal, inside the warning limit
        (2.0, 4.0),  # Warning, above the warning limit on the positive side
        (-4.0, -2.0),  # Warning, on the negative side
        (4.0, scale),  # Abnormal, above the abnormal limit
        (-scale, -4.0),  # Abnormal, below the negative abnormal limit
    }


def test_fault_injected_in_the_hmi_shows_in_the_charts_and_event_log(qtbot):
    window = window_with(qtbot, config=midday_config())
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = window.process_view
    view.start_button.click()
    window.playback.tick()

    view.fault_buttons[FaultKind.PARTIAL_SHADING].click()
    for _ in range(3):
        window.playback.tick()
    dashboard.refresh()

    texts = event_texts(dashboard)
    assert any("Fault: none -> partial shading" in text for text in texts)
    assert any("State: Normal -> Abnormal" in text for text in texts)
    assert dashboard.tiles["state"].text() == "Abnormal"
    assert dashboard.tiles["state"].colour() == STATE_COLOURS[State.ABNORMAL]
    expected = [sample.deviation_pct for sample in window.history.samples_from(0)]
    assert np.allclose(plotted_deviation(dashboard), expected)
    assert min(expected) < -10.0  # the shading drop shows as a deep negative deviation


def test_a_full_day_is_plotted_in_one_update_per_curve_per_ui_tick(qtbot, plot_calls):
    window = window_with(qtbot)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    window.process_view.start_button.click()
    while window.playback.is_running:
        window.playback.tick()  # the bus fills the history; the Dashboard has not ticked yet
    assert window.history.sample_count == 1381

    plot_calls.clear()
    dashboard.refresh()

    assert len(plot_calls) == CURVE_COUNT
    assert len(plotted_deviation(dashboard)) == 1381


def test_a_ui_tick_with_nothing_new_plots_nothing(qtbot, plot_calls):
    window = window_with(qtbot, config=midday_config())
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    window.process_view.start_button.click()
    window.playback.tick()
    dashboard.refresh()

    plot_calls.clear()
    dashboard.refresh()  # nothing has arrived since the last tick
    window.playback.pause()
    window.playback.tick()  # paused, so the bus stays quiet
    dashboard.refresh()

    assert plot_calls == []


def test_closing_the_dashboard_leaves_the_hmi_running_and_reopening_shows_the_history(qtbot):
    window = window_with(qtbot, config=midday_config())
    view = window.process_view
    view.start_button.click()
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    window.playback.tick()
    dashboard.refresh()

    dashboard.close()
    assert not dashboard.isVisible()
    assert window.playback.is_running
    for _ in range(3):
        window.playback.tick()  # the run goes on while the Dashboard is closed
    assert window.playback.is_running

    reopened = window.open_dashboard()

    assert reopened.isVisible()
    assert len(plotted_deviation(reopened)) == window.history.sample_count
    assert reopened.tiles["p_measured"].text() == format_readings(window.history.latest)["P"]


def test_a_dashboard_opened_mid_run_shows_the_history_so_far_including_faults(qtbot):
    window = window_with(qtbot, config=midday_config())
    window.process_view.start_button.click()
    window.playback.tick()
    window.playback.inject(default_fault(FaultKind.SOILING))
    for _ in range(3):
        window.playback.tick()

    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)

    assert len(plotted_deviation(dashboard)) == window.history.sample_count
    assert any("Fault: none -> soiling" in text for text in event_texts(dashboard))


def test_reset_clears_the_dashboard(qtbot):
    window = window_with(qtbot, config=midday_config())
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = window.process_view
    view.start_button.click()
    window.playback.tick()
    window.playback.inject(default_fault(FaultKind.SOILING))
    window.playback.tick()
    dashboard.refresh()

    view.reset_button.click()
    dashboard.refresh()

    assert plotted_deviation(dashboard).size == 0
    assert event_texts(dashboard) == []
    assert dashboard.tiles["p_measured"].text() == PLACEHOLDER
    assert dashboard.tiles["state"].colour() is None


def test_offscreen_smoke_opens_the_dashboard_and_logs_events_for_a_run_with_a_fault(qtbot):
    window = Session().open_hmi()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.playback.set_speed(FASTEST)
    window.open_dashboard_action.trigger()
    dashboard = window.open_dashboard()
    qtbot.waitExposed(dashboard)
    view = window.process_view

    view.start_button.click()
    for _ in range(5):
        window.playback.tick()
    view.fault_buttons[FaultKind.SENSOR_DRIFT].click()
    for _ in range(5):
        window.playback.tick()
    dashboard.refresh()
    dashboard.grab()

    assert dashboard.isWindow() and dashboard.isVisible()
    assert dashboard.windowTitle() == "PV Digital Twin Dashboard"
    assert dashboard.event_list.count() > 0
    assert any("Fault:" in text for text in event_texts(dashboard))
    dashboard.close()
    window.close()
    assert not window.isVisible()


IDLE_MESSAGE = "No run in progress. Start a run from the HMI."


def test_dashboard_opened_alone_without_a_run_says_how_to_start_one(qtbot):
    session = Session(config=midday_config())
    dashboard = session.open_dashboard()
    qtbot.addWidget(dashboard)

    assert dashboard.idle_message.text() == IDLE_MESSAGE
    assert dashboard.idle_message.isVisible()
    assert not dashboard.overview.isVisible()


def test_idle_open_hmi_button_opens_the_hmi(qtbot):
    session = Session(config=midday_config())
    dashboard = session.open_dashboard()
    qtbot.addWidget(dashboard)

    dashboard.open_hmi_button.click()

    assert session.hmi_open
    qtbot.addWidget(session.hmi)


def test_idle_message_gives_way_to_the_overview_once_samples_arrive(qtbot):
    session = Session(config=midday_config())
    session.playback.set_speed(FASTEST)
    dashboard = session.open_dashboard()
    qtbot.addWidget(dashboard)

    session.playback.start()
    session.playback.tick()
    dashboard.refresh()

    assert dashboard.overview.isVisible()
    assert not dashboard.idle_message.isVisible()


def test_dashboard_with_the_hmi_open_shows_the_overview_before_a_run(qtbot):
    session = Session(config=midday_config())
    hmi = session.open_hmi()
    qtbot.addWidget(hmi)
    dashboard = session.open_dashboard()
    qtbot.addWidget(dashboard)

    dashboard.refresh()

    assert dashboard.overview.isVisible()
