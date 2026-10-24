from dataclasses import replace

import pytest

from pvysics.gui.process_view import format_readings
from pvysics.gui.session import Session
from pvysics.profile import Profile
from pvysics.run import bundled_run_config

FASTEST = 28800.0


def midday_config():
    """The bundled day cut to 10:00 to 14:00, so a few ticks cover it."""
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
    return session


def track(qtbot, window):
    qtbot.addWidget(window)
    return window


def test_session_owns_one_run_shared_by_both_windows(qtbot, session):
    hmi = track(qtbot, session.open_hmi())
    dashboard = track(qtbot, session.open_dashboard())

    assert hmi.playback is session.playback
    assert dashboard._history is session.history
    assert hmi.theme is session.theme


def test_one_run_feeds_the_hmi_and_the_dashboard(qtbot, session):
    hmi = track(qtbot, session.open_hmi())
    dashboard = track(qtbot, session.open_dashboard())
    hmi.process_view.start_button.click()
    for _ in range(3):
        session.playback.tick()
    dashboard.refresh()

    _x, plotted = dashboard._deviation.getData()
    assert len(plotted) == session.history.sample_count > 0
    assert dashboard.strip.value("p_predicted") == format_readings(session.history.latest)["P_pred"]


def test_closing_either_window_leaves_the_other_and_the_run_going(qtbot, session):
    hmi = track(qtbot, session.open_hmi())
    dashboard = track(qtbot, session.open_dashboard())
    hmi.process_view.start_button.click()
    session.playback.tick()

    hmi.close()
    session.playback.tick()
    assert dashboard.isVisible()
    assert session.playback.is_running
    dashboard.close()
    session.playback.tick()
    assert session.playback.is_running
    assert session.history.sample_count > 1


def test_a_window_already_open_is_raised_not_duplicated(qtbot, session, monkeypatch):
    first = track(qtbot, session.open_hmi())
    raised = []
    monkeypatch.setattr(first, "raise_", lambda: raised.append(True))

    second = session.open_hmi()

    assert second is first
    assert second.isVisible()
    assert raised == [True]


def test_a_closed_window_is_shown_again_not_recreated(qtbot, session):
    dashboard = track(qtbot, session.open_dashboard())
    dashboard.close()

    reopened = session.open_dashboard()

    assert reopened is dashboard
    assert reopened.isVisible()


def test_dashboard_reopened_after_the_run_shows_the_history_so_far(qtbot, session):
    hmi = track(qtbot, session.open_hmi())
    dashboard = track(qtbot, session.open_dashboard())
    hmi.process_view.start_button.click()
    session.playback.tick()
    dashboard.close()
    for _ in range(3):
        session.playback.tick()

    session.open_dashboard()
    dashboard.refresh()

    _x, plotted = dashboard._deviation.getData()
    assert len(plotted) == session.history.sample_count


def test_hmi_built_on_a_session_has_its_window_menu_entries(qtbot, session):
    hmi = track(qtbot, session.open_hmi())

    assert hmi.open_dashboard_action.text() == "Open Dashboard"

