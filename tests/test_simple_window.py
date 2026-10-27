import csv
from dataclasses import replace

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from pvysics.faults import FaultKind, default_fault
from pvysics.gui.metric_strip import split_reading
from pvysics.gui.palette import CHOICE_DARK, CHOICE_LIGHT, DARK, LIGHT
from pvysics.gui.playback import SPEEDS
from pvysics.gui.process_view import format_readings
from pvysics.gui.session import Session
from pvysics.gui.simple_pages import EMPTY, WAITING
from pvysics.gui.simple_window import (
    ANALYSIS,
    DASHBOARD,
    DATA,
    EVENT_LOG,
    PAGE_NAMES,
    SDM_MODEL,
    SETTINGS,
    TRENDS,
)
from pvysics.profile import Profile
from pvysics.run import State, bundled_run_config

FASTEST = SPEEDS[-1]


def midday_config():
    """The bundled day cut to 10:00 to 14:00, so a few ticks at the fastest speed cover it."""
    config = bundled_run_config(seed=1)
    profile = config.profile
    cut = Profile(
        timestamps=profile.timestamps[10:15],
        irradiance=profile.irradiance[10:15],
        temperature=profile.temperature[10:15],
    )
    return replace(config, profile=cut)


def make_window(qtbot, session=None):
    session = session or Session(config=midday_config())
    session.playback.set_speed(FASTEST)
    window = session.open_simple()
    qtbot.addWidget(window)
    return window


@pytest.fixture
def window(qtbot):
    return make_window(qtbot)


def run_with_fault(window, ticks=3):
    window.dashboard_page.toolbar.start_button.click()
    window.playback.tick()
    window.dashboard_page.toolbar.fault_buttons[FaultKind.PARTIAL_SHADING].click()
    for _ in range(ticks):
        window.playback.tick()


def test_the_session_opens_one_simple_window_and_raises_it_again(window):
    assert window.isVisible()
    assert window.session.open_simple() is window
    assert window.session.hmi is None
    assert window.session.dashboard is None


def test_the_sidebar_lists_the_pages_and_opens_on_the_dashboard(window):
    assert list(window.nav_buttons) == list(PAGE_NAMES)
    assert window.current_page_name == DASHBOARD
    assert window.nav_buttons[DASHBOARD].isChecked()


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_each_sidebar_button_brings_its_page_to_the_front(window, name):
    window.nav_buttons[name].click()

    assert window.current_page_name == name
    assert window.nav_buttons[name].isChecked()
    assert sum(button.isChecked() for button in window.nav_buttons.values()) == 1


def hide_the_sidebar(window):
    window.hide_button.click()
    assert window.sidebar.isHidden()
    assert not window.rail.isHidden()


def test_hide_hides_the_sidebar_and_leaves_a_rail_with_a_show_button(window):
    hide_the_sidebar(window)

    assert window.show_button.isVisibleTo(window)
    assert not window.sidebar_action.isChecked()


def test_the_rail_button_shows_the_sidebar_again(window):
    hide_the_sidebar(window)

    window.show_button.click()

    assert window.sidebar_visible
    assert window.rail.isHidden()
    assert not window.hide_button.isChecked()
    assert window.sidebar_action.isChecked()


def test_view_sidebar_toggles_the_sidebar_both_ways(window):
    window.sidebar_action.trigger()
    assert not window.sidebar_visible
    assert window.hide_button.isChecked()

    window.sidebar_action.trigger()

    assert window.sidebar_visible
    assert not window.hide_button.isChecked()


def test_escape_shows_the_sidebar_again(window):
    hide_the_sidebar(window)

    QTest.keyClick(window, Qt.Key.Key_Escape)

    assert window.sidebar_visible
    assert window.rail.isHidden()


def test_the_window_follows_the_chosen_theme(window):
    window.theme.set_choice(CHOICE_LIGHT)
    assert LIGHT.card in window.styleSheet()

    window.theme.set_choice(CHOICE_DARK)

    assert DARK.card in window.styleSheet()
    assert LIGHT.card not in window.styleSheet()


def test_the_view_menu_offers_the_themes_and_the_log(window):
    assert [action.text() for action in window.menuBar().actions()] == ["&View"]
    assert set(window.theme_menu.actions) == {"system", "light", "dark"}
    view_actions = window.menuBar().actions()[0].menu().actions()
    assert window.log_pane.view_action in view_actions
    assert window.sidebar_action in view_actions


def test_dashboard_shows_dashes_and_waiting_before_a_run(window):
    page = window.dashboard_page

    assert all(kpi.text == EMPTY for kpi in page.kpis.values())
    assert page.state_text == f"SYSTEM STATE: {WAITING}"
    assert page.tiles["samples"].text == "0"
    assert "NORMAL ≤ 5%" in page.limits_label.text()
    assert "ABNORMAL > 10%" in page.limits_label.text()


def test_dashboard_readings_follow_every_sample(window):
    window.dashboard_page.toolbar.start_button.click()
    window.playback.tick()

    expected = format_readings(window.session.history.latest)
    for key, kpi in window.dashboard_page.kpis.items():
        assert kpi.text == split_reading(expected[key])[0]


def test_dashboard_deviation_card_shows_the_state_peak_energy_and_count(window):
    page = window.dashboard_page
    run_with_fault(window)

    latest = window.session.history.latest
    assert latest.state is State.ABNORMAL
    assert page.state_text == "SYSTEM STATE: ABNORMAL"
    assert page.deviation_label.text() == f"{latest.deviation_pct:+.1f} %"
    assert page.tiles["samples"].text == str(window.session.history.sample_count)
    assert float(page.tiles["peak"].text) >= latest.power_measured
    assert float(page.tiles["energy"].text) == pytest.approx(window.session.history.energy_wh, abs=0.05)
    assert page.tiles["elapsed"].text != "00:00:00"


def test_reset_returns_the_dashboard_to_waiting(window):
    run_with_fault(window)

    window.dashboard_page.toolbar.reset_button.click()

    page = window.dashboard_page
    assert page.state_text == f"SYSTEM STATE: {WAITING}"
    assert all(kpi.text == EMPTY for kpi in page.kpis.values())
    assert page.tiles["samples"].text == "0"
    assert page.trend.point_count == 0


def test_a_window_opened_mid_run_shows_the_run_so_far(qtbot):
    session = Session(config=midday_config())
    session.playback.set_speed(FASTEST)
    session.playback.start()
    for _ in range(3):
        session.playback.tick()

    window = make_window(qtbot, session)

    page = window.dashboard_page
    assert page.kpis["P"].text == split_reading(format_readings(session.history.latest)["P"])[0]
    assert page.tiles["samples"].text == str(session.history.sample_count)
    assert page.trend.point_count == session.history.sample_count


def test_open_event_log_button_goes_to_the_event_log(window):
    window.dashboard_page.event_log_button.click()

    assert window.current_page_name == EVENT_LOG


def test_an_injected_fault_is_listed_as_an_alarm_and_as_events(window):
    run_with_fault(window)
    window.nav_buttons[EVENT_LOG].click()

    page = window.event_log_page
    assert page.alarm_panel.list_widget.count() > 0
    assert page.alarm_panel.summary_label.text().endswith("new")
    texts = [page.event_list.item(row).text() for row in range(page.event_list.count())]
    assert any("partial shading" in text for text in texts)
    assert any("Abnormal" in text for text in texts)


def test_an_event_log_opened_late_lists_the_events_so_far(qtbot):
    session = Session(config=midday_config())
    session.playback.set_speed(FASTEST)
    session.playback.start()
    session.playback.tick()
    session.playback.inject(default_fault(FaultKind.SOILING))
    session.playback.tick()

    window = make_window(qtbot, session)

    assert window.event_log_page.event_list.count() == session.history.event_count > 0


def test_the_log_button_opens_the_log_pop_up(window):
    assert not window.log_pane.isVisible()

    window.event_log_page.log_button.click()

    assert window.log_pane.isVisible()


def test_trends_chart_every_channel_once_the_page_is_shown(window):
    window.dashboard_page.toolbar.start_button.click()
    for _ in range(3):
        window.playback.tick()

    window.nav_buttons[TRENDS].click()

    page = window.trends_page
    assert set(page.plots) == {"irradiance", "temperature", "voltage", "current", "power_measured"}
    for column, curve in page._curves.items():
        x, y = curve.getData()
        assert len(y) == window.session.history.sample_count > 0, column


def test_data_lists_the_newest_sample_first_and_caps_the_rows(window):
    window.dashboard_page.toolbar.start_button.click()
    for _ in range(3):
        window.playback.tick()

    window.nav_buttons[DATA].click()

    page = window.data_page
    history = window.session.history
    assert page.row_count == history.sample_count
    assert page.table.item(0, 5).text() == f"{history.latest.power_measured:.1f}"


def test_data_export_writes_every_sample_of_the_run(window, tmp_path):
    window.dashboard_page.toolbar.start_button.click()
    for _ in range(3):
        window.playback.tick()
    path = tmp_path / "run.csv"

    window.data_page.export_csv(str(path))

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) - 1 == window.session.history.sample_count


def test_analysis_and_model_pages_hold_the_advanced_views(window):
    assert window.analysis_page.validation.run_button.text() == "Run validation"
    assert window.model_page.model_view is not None
    window.nav_buttons[ANALYSIS].click()
    window.nav_buttons[SDM_MODEL].click()
    assert window.current_page_name == SDM_MODEL


def test_applying_settings_starts_a_new_run_and_returns_to_the_dashboard(window):
    window.dashboard_page.toolbar.start_button.click()
    window.playback.tick()
    window.nav_buttons[SETTINGS].click()
    new_config = replace(window.session.config, seed=7)

    window.settings_page.setup_view.apply_requested.emit(new_config)

    assert window.session.config.seed == 7
    assert window.current_page_name == DASHBOARD
    assert window.session.history.sample_count <= 1  # a fresh run, not the old one's samples
