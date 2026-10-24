from dataclasses import replace

import numpy as np
import pyqtgraph as pg
import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from pvysics.faults import FaultKind, default_fault
from pvysics.gui import live_charts
from pvysics.gui.dashboard import SampleColumns
from pvysics.gui.live_charts import LiveCharts
from pvysics.gui.palette import DARK, LIGHT, STATE_COLOURS
from pvysics.gui.playback import SPEEDS
from pvysics.gui.session import Session
from pvysics.gui.theme import ThemeManager
from pvysics.live_stats import DeviationHistogram, StateTimes
from pvysics.profile import Profile
from pvysics.run import POWER_FLOOR_W, RunConfig, SensorModel, State, bundled_run_config, run
from pvysics.single_diode import fit_parameters, solve_curve

FASTEST = SPEEDS[-1]
LIVE_CURVES_PER_TICK = 3  # energy, I-V and P-V (the operating points are scatter items)
NOISE_FREE = SensorModel(
    irradiance_noise_pct=0.0,
    temperature_noise_c=0.0,
    voltage_noise_v=0.0,
    current_noise_a=0.0,
    voltage_step_v=0.0,
    current_step_a=0.0,
)


def midday_config(sensors: SensorModel | None = None) -> RunConfig:
    """The bundled day cut to 10:00 to 14:00, one Sample a minute."""
    config = bundled_run_config(seed=1)
    profile = config.profile
    cut = Profile(
        timestamps=profile.timestamps[10:15],
        irradiance=profile.irradiance[10:15],
        temperature=profile.temperature[10:15],
    )
    config = replace(config, profile=cut)
    return config if sensors is None else replace(config, sensors=sensors)


def window_with(qtbot, config: RunConfig | None = None, theme: ThemeManager | None = None):
    session = Session(config=midday_config() if config is None else config, theme=theme)
    window = session.open_hmi()
    qtbot.addWidget(window)
    window.playback.set_speed(FASTEST)
    return window


@pytest.fixture
def plot_calls(monkeypatch) -> list:
    """Records every curve update made through pyqtgraph's PlotDataItem."""
    calls = []
    original = pg.PlotDataItem.setData

    def recording(self, *args, **kwargs):
        calls.append(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pg.PlotDataItem, "setData", recording)
    return calls


@pytest.fixture
def add_calls(monkeypatch) -> list:
    """Records how many Samples each headless statistic is given per call."""
    calls = []
    for cls in (DeviationHistogram, StateTimes):
        original = cls.add

        def recording(self, samples, _original=original):
            samples = list(samples)
            calls.append((type(self), len(samples)))
            return _original(self, samples)

        monkeypatch.setattr(cls, "add", recording)
    return calls


def plotted_values(curve) -> np.ndarray:
    _x, y = curve.getData()
    return np.array([] if y is None else y)


def daylight_count(samples) -> int:
    return sum(1 for sample in samples if sample.power_predicted >= POWER_FLOOR_W)


def test_the_dashboard_has_an_overview_that_holds_the_live_charts_and_a_validation_tab(qtbot):
    window = window_with(qtbot)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    tabs = dashboard.centralWidget()

    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Overview", "Validation"]
    for box in (dashboard.live.curves_box, dashboard.live.energy_box,
                dashboard.live.histogram_box, dashboard.live.states_box):
        assert dashboard.charts.isAncestorOf(box)  # the live charts are docks in the Overview, not a tab of their own


def test_each_live_chart_has_data_after_a_short_run(qtbot):
    window = window_with(qtbot)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    window.process_view.start_button.click()
    for _ in range(3):
        window.playback.tick()
    dashboard.refresh()
    live, history = dashboard.live, window.history
    count = history.sample_count

    _x, energy_y = live._energy.getData()
    _x, iv_y = live._iv_curve.getData()
    _x, pv_y = live._pv_curve.getData()
    latest = history.latest
    assert len(energy_y) == count
    assert energy_y[-1] == pytest.approx(history.energy_wh)
    assert len(iv_y) == len(pv_y) == 500 and live.curve is not None
    point_x, point_y = live._iv_point.getData()
    assert point_x[0] == pytest.approx(latest.measured_voltage)
    assert point_y[0] == pytest.approx(latest.measured_current)
    assert live.histogram.total == daylight_count(history.samples_from(0))
    assert live.state_times.total_seconds == pytest.approx(
        (latest.timestamp - history.origin) / np.timedelta64(1, "s")
    )
    assert live.histogram.total > 0


def test_operating_curves_match_the_model_tab_curve_for_the_measured_gt(qtbot):
    config = midday_config()
    window = window_with(qtbot, config=config)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    window.process_view.start_button.click()
    for _ in range(3):
        window.playback.tick()
    dashboard.refresh()
    latest = window.history.latest

    expected = solve_curve(
        config.datasheet, latest.measured_irradiance, latest.measured_temperature, fit_parameters(config.datasheet)
    )
    assert dashboard.live.curve_key == (latest.measured_irradiance, latest.measured_temperature)
    assert np.allclose(dashboard.live.curve.current, expected.current)
    assert dashboard.live.curve.mpp_power == pytest.approx(latest.power_predicted)


def test_at_night_the_last_daylight_curve_stays_on_show(qtbot):
    config = midday_config(sensors=NOISE_FREE)
    samples = run(config).samples
    dark = replace(samples[-1], measured_irradiance=0.0, power_predicted=0.0, power_measured=0.0,
                   measured_voltage=0.0, measured_current=0.0)
    live = LiveCharts(config.datasheet, LIGHT)
    qtbot.addWidget(live)
    columns = SampleColumns()
    columns.append(samples, samples[0].timestamp, [0.0] * len(samples))
    live.update(columns, samples)
    daylight_curve = live.curve

    columns.append([dark], samples[0].timestamp, [0.0])
    live.update(columns, [dark])

    assert live.curve is daylight_curve  # the curve is not recomputed for a night Sample
    assert plotted_values(live._iv_point).size == 1  # the operating point still moves
    assert live._iv_point.getData()[0][0] == 0.0


def test_a_tick_that_ends_at_night_still_shows_the_daylight_curve_it_passed(qtbot):
    config = midday_config(sensors=NOISE_FREE)
    samples = run(config).samples
    dark = replace(samples[-1], measured_irradiance=0.0, power_predicted=0.0, power_measured=0.0)
    live = LiveCharts(config.datasheet, LIGHT)
    qtbot.addWidget(live)
    columns = SampleColumns()
    batch = samples + [dark]
    columns.append(batch, samples[0].timestamp, [0.0] * len(batch))

    live.update(columns, batch)  # one UI tick that covers the day and ends at night

    assert live.curve_key == (samples[-1].measured_irradiance, samples[-1].measured_temperature)
    assert live.curve is not None and live.curve.mpp_power == pytest.approx(samples[-1].power_predicted)


def test_operating_curves_are_recomputed_only_when_g_or_t_changes(qtbot, monkeypatch):
    config = midday_config(sensors=NOISE_FREE)
    samples = run(config).samples
    calls = []
    real = live_charts.solve_curve

    def counting(*args, **kwargs):
        calls.append(args[1:3])
        return real(*args, **kwargs)

    monkeypatch.setattr(live_charts, "solve_curve", counting)
    live = LiveCharts(config.datasheet, LIGHT)
    qtbot.addWidget(live)
    columns = SampleColumns()
    keys = [(sample.measured_irradiance, sample.measured_temperature) for sample in samples]
    expected = 1 + sum(1 for before, after in zip(keys, keys[1:]) if before != after)

    for sample in samples:
        columns.append([sample], samples[0].timestamp, [0.0])
        live.update(columns, [sample])
    assert len(calls) == expected
    assert expected > 1  # G and T moved over the day

    columns.append([samples[-1]], samples[0].timestamp, [0.0])
    live.update(columns, [samples[-1]])  # the same G and T again
    assert len(calls) == expected


def test_histogram_and_state_times_take_only_the_new_samples_each_tick(qtbot, add_calls):
    window = window_with(qtbot, config=bundled_run_config(seed=1))
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    window.process_view.start_button.click()
    seen = 0
    ticks_with_samples = 0
    while window.playback.is_running:
        window.playback.tick()
        new = window.history.sample_count - seen
        seen = window.history.sample_count
        add_calls.clear()
        dashboard.refresh()
        if new:
            ticks_with_samples += 1
            assert sorted(size for _cls, size in add_calls) == [new, new]  # one call per statistic
        else:
            assert add_calls == []

    assert ticks_with_samples > 1
    assert seen == 1381  # the whole day: every Sample was counted once by each statistic
    assert dashboard.live.state_times.total_seconds == pytest.approx(1380 * 60.0)
    assert dashboard.live.histogram.total == daylight_count(window.history.samples_from(0))


def test_a_full_day_plots_each_live_curve_once_per_ui_tick(qtbot, plot_calls):
    window = window_with(qtbot)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    window.process_view.start_button.click()
    while window.playback.is_running:
        window.playback.tick()

    plot_calls.clear()
    dashboard.refresh()
    live_curves = (
        dashboard.live._energy,
        dashboard.live._iv_curve,
        dashboard.live._pv_curve,
    )
    live_calls = [curve for curve in plot_calls if curve in live_curves]

    assert len(live_calls) == LIVE_CURVES_PER_TICK
    assert len(set(map(id, live_calls))) == LIVE_CURVES_PER_TICK  # one update each, never repeated
    assert dashboard.live.histogram.total == daylight_count(window.history.samples_from(0))


def test_reset_clears_every_live_chart(qtbot):
    window = window_with(qtbot)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = window.process_view
    view.start_button.click()
    for _ in range(3):
        window.playback.tick()
    dashboard.refresh()

    view.reset_button.click()
    dashboard.refresh()

    live = dashboard.live
    for curve in (live._energy, live._iv_curve, live._pv_curve):
        assert plotted_values(curve).size == 0
    assert live._iv_point.data["x"].size == 0
    assert live.curve is None
    assert live.histogram.total == 0
    assert live.state_times.total_seconds == 0.0
    assert np.all(live._histogram_bars.opts["height"] == 0)


def test_reopening_the_dashboard_mid_run_shows_the_history_in_the_live_charts(qtbot):
    window = window_with(qtbot)
    window.process_view.start_button.click()
    window.playback.tick()
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    dashboard.close()
    for _ in range(3):
        window.playback.tick()  # the run goes on while the Dashboard is closed

    reopened = window.open_dashboard()

    assert reopened.isVisible()
    _x, energy = reopened.live._energy.getData()
    assert len(energy) == window.history.sample_count
    assert reopened.live.histogram.total == daylight_count(window.history.samples_from(0))
    assert reopened.live.state_times.total_seconds == pytest.approx(
        (window.history.latest.timestamp - window.history.origin) / np.timedelta64(1, "s")
    )


def test_live_charts_follow_the_theme_and_a_new_chart_starts_in_the_current_theme(qtbot, tmp_path):
    theme = ThemeManager(QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat))
    theme.set_choice("dark")
    window = window_with(qtbot, theme=theme)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    live = dashboard.live

    for plot in (live.iv_plot, live.pv_plot, live.energy_plot,
                 live.histogram_plot, live.state_plot):
        assert plot.backgroundBrush().color() == QColor(DARK.chart_background)
        assert plot.getAxis("left").pen().color() == QColor(DARK.muted_text)
    assert live._energy.opts["pen"].color() == QColor(DARK.measured)

    theme.set_choice("light")

    assert live.iv_plot.backgroundBrush().color() == QColor(LIGHT.chart_background)
    assert live._energy.opts["pen"].color() == QColor(LIGHT.measured)
    assert live._iv_point.opts["brush"].color() == QColor(LIGHT.operating_point)


def test_state_time_bars_use_the_palette_state_colours(qtbot):
    window = window_with(qtbot)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    brushes = dashboard.live._state_bars.opts["brushes"]

    assert [brush.color() for brush in brushes] == [
        QColor(STATE_COLOURS[State.NORMAL]),
        QColor(STATE_COLOURS[State.WARNING]),
        QColor(STATE_COLOURS[State.ABNORMAL]),
    ]


def test_the_overview_shows_the_idle_message_when_no_run_is_in_progress(qtbot):
    session = Session(config=midday_config())
    dashboard = session.open_dashboard()
    qtbot.addWidget(dashboard)

    assert dashboard._idle_page.isVisible()
    assert not dashboard.overview.isVisible()


def test_the_overview_docks_every_chart_at_1280_by_800_and_plots_keep_their_height(qtbot):
    window = window_with(qtbot)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    dashboard.resize(1280, 800)
    window.process_view.start_button.click()
    window.playback.tick()
    dashboard.refresh()
    QApplication.processEvents()

    live = dashboard.live
    for plot in (live.iv_plot, live.pv_plot, live.energy_plot,
                 live.histogram_plot, live.state_plot):
        assert plot.height() >= plot.minimumHeight()


def test_offscreen_smoke_runs_a_short_run_with_a_fault_and_the_live_charts_have_data(qtbot):
    window = Session(config=midday_config()).open_hmi()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.playback.set_speed(FASTEST)
    dashboard = window.open_dashboard()
    qtbot.waitExposed(dashboard)
    dashboard.centralWidget().setCurrentIndex(1)
    view = window.process_view

    view.start_button.click()
    for _ in range(3):
        window.playback.tick()
    window.playback.inject(default_fault(FaultKind.PARTIAL_SHADING))
    for _ in range(5):
        window.playback.tick()
    dashboard.refresh()
    dashboard.grab()

    live = dashboard.live
    assert live.histogram.total > 0
    assert live.state_times.seconds_in(State.ABNORMAL) > 0.0
    assert live.histogram.below_range + live.histogram.above_range + live.histogram.total == daylight_count(
        window.history.samples_from(0)
    )
    assert len(live._energy.getData()[1]) == window.history.sample_count
    assert live.curve is not None
    assert "Abnormal" in live.state_caption.text()
    dashboard.close()
    window.close()
