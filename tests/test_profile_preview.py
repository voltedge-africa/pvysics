"""The fetched-profile preview: its charts and statistics, theming, Use profile, Discard, closing without a
choice, failed fetches, a 31-day range and a smoke run. Every fetch uses a fake transport; none touches the network.
"""

import logging
import urllib.error
from datetime import date

import numpy as np
import pytest
from PyQt6.QtCore import QDate, QSettings
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel

from pvysics.fetch import ProfileFetcher
from pvysics.gui.palette import DARK, LIGHT
from pvysics.gui.profile_preview import TimeAxis
from pvysics.gui.session import Session
from pvysics.gui.theme import ThemeManager
from pvysics.profile_stats import MAX_PLOT_POINTS
from pvysics.run import bundled_run_config
from test_fetch import FakeTransport, bundled_rows, response_text

WAIT_MS = 10000


def window_and_panel(qtbot, tmp_path, transport, theme: ThemeManager | None = None):
    session = Session(config=bundled_run_config(), theme=theme)
    window = session.open_hmi()
    qtbot.addWidget(window)
    setup = window.setup_view
    setup.fetch_panel.set_fetcher(ProfileFetcher(transport, tmp_path))
    return window, setup, setup.fetch_panel


def fetch(qtbot, panel) -> None:
    panel.start_fetch()
    qtbot.waitUntil(lambda: not panel.is_running, timeout=WAIT_MS)


def set_range(panel, start: date, end: date) -> None:
    panel.start_edit.setDate(QDate(start.year, start.month, start.day))
    panel.end_edit.setDate(QDate(end.year, end.month, end.day))


def label_text(dialog) -> str:
    return "\n".join(label.text() for label in dialog.findChildren(QLabel))


def thirty_one_day_text() -> str:
    """31 days of hourly rows in January 2025: sun from 06:00 to 17:00, a higher peak each day, 20 C to 22.3 C."""
    rows = []
    for day in range(1, 32):
        for hour in range(24):
            irradiance = (100.0 + 10.0 * day) if 6 <= hour < 18 else 0.0
            rows.append(f"2025,1,{day},{hour},{irradiance:.1f},{20.0 + hour / 10:.1f}")
    return response_text(rows=rows)


def bundled_at_33_degrees() -> str:
    """The bundled days with every temperature set to 33.3 C, so a run can show which profile it used."""
    rows = [",".join(row.split(",")[:4] + [row.split(",")[4], "33.3"]) for row in bundled_rows()]
    return response_text(rows=rows)


# Charts and statistics

def test_a_successful_fetch_opens_a_preview_with_both_charts_and_the_statistics(qtbot, tmp_path):
    _window, _setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(response_text()))

    fetch(qtbot, panel)

    dialog = panel.preview_dialog
    assert dialog is not None and dialog.isVisible()
    assert len(dialog.irradiance_curve.getData()[0]) == 72
    assert len(dialog.temperature_curve.getData()[0]) == 72
    assert isinstance(dialog.irradiance_plot.getAxis("bottom"), TimeAxis)
    assert isinstance(dialog.temperature_plot.getAxis("bottom"), TimeAxis)
    text = label_text(dialog)
    assert "72, every 1 h" in text
    assert "2025-01-15 00:00" in text and "2025-01-17 23:00" in text
    assert "Source: NASA POWER at latitude -29.85, longitude 31; " in text
    assert "(3 days)" in text
    assert "all-sky irradiance" in text and "local standard time (LST)" in text and "from the network" in text
    assert "- no negative irradiance" in text  # the checks that passed are listed


def test_the_statistics_in_the_preview_are_those_of_the_staged_profile(qtbot, tmp_path):
    _window, _setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(response_text()))

    fetch(qtbot, panel)

    stats = panel.preview_dialog.stats
    assert stats is not None
    assert stats.samples == 72 and stats.days == 3
    assert stats.peak_g == pytest.approx(panel.staged_profile.irradiance.max())
    assert stats.mean_t == pytest.approx(panel.staged_profile.temperature.mean())
    assert len(stats.daily_peak_g) == 3


def test_the_preview_charts_follow_the_theme_and_a_new_preview_starts_in_the_current_theme(qtbot, tmp_path):
    theme = ThemeManager(QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat))
    theme.set_choice("dark")
    _window, _setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(response_text()), theme=theme)
    fetch(qtbot, panel)
    dialog = panel.preview_dialog

    for plot in (dialog.irradiance_plot, dialog.temperature_plot):
        assert plot.backgroundBrush().color() == QColor(DARK.chart_background)
        assert plot.getAxis("left").pen().color() == QColor(DARK.muted_text)
    assert dialog.irradiance_curve.opts["pen"].color() == QColor(DARK.irradiance)
    assert dialog.temperature_curve.opts["pen"].color() == QColor(DARK.temperature)

    theme.set_choice("light")

    assert dialog.irradiance_plot.backgroundBrush().color() == QColor(LIGHT.chart_background)
    assert dialog.temperature_curve.opts["pen"].color() == QColor(LIGHT.temperature)

    dialog.reject()
    theme.set_choice("dark")
    panel.preview_button.click()

    assert panel.preview_dialog.temperature_plot.backgroundBrush().color() == QColor(DARK.chart_background)


def test_the_time_axis_labels_days_and_times_of_day(qtbot):
    axis = TimeAxis(np.datetime64("2025-01-01T00:00"))

    assert axis.tickStrings([0.0, 24.0, 48.0], 1.0, 24.0) == ["01 Jan", "02 Jan", "03 Jan"]
    assert axis.tickStrings([6.0, 12.0], 1.0, 6.0) == ["01 Jan 06:00", "01 Jan 12:00"]


@pytest.mark.parametrize(
    ("days", "step_h"),
    [(3, 12.0), (10, 24.0), (31, 168.0)],
    ids=["three-days", "ten-days", "thirty-one-days"],
)
def test_the_time_axis_ticks_fall_on_round_times_and_stay_few(qtbot, days, step_h):
    axis = TimeAxis(np.datetime64("2025-01-01T00:00"))

    ((spacing, values),) = axis.tickValues(0.0, 24.0 * days, 500)

    assert spacing == pytest.approx(step_h)
    assert values[0] == pytest.approx(0.0)
    assert len(values) <= 10


# Use, Discard and closing

def test_use_profile_makes_the_staged_profile_active_and_it_is_in_the_run_summary(qtbot, tmp_path):
    _window, setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(response_text()))
    fetch(qtbot, panel)
    staged = panel.staged_profile

    panel.preview_dialog.use_button.click()

    assert setup.read_config().profile is staged
    assert staged.name in setup.summary_label.text()
    assert staged.name in setup.message
    assert panel.preview_dialog is None


def test_discard_drops_the_staged_profile_and_the_previous_active_profile_stays(qtbot, tmp_path, caplog):
    _window, setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(response_text()))
    active = setup.read_config().profile
    fetch(qtbot, panel)

    with caplog.at_level(logging.DEBUG, logger="pvysics"):
        panel.preview_dialog.discard_button.click()

    assert panel.staged_profile is None
    assert not panel.preview_button.isEnabled()
    assert panel.preview_dialog is None
    assert setup.read_config().profile is active
    assert "Discarded" in setup.message
    assert any(r.levelno == logging.INFO and "discarded" in r.getMessage() for r in caplog.records)


def test_closing_the_preview_without_choosing_keeps_the_profile_staged_and_it_reopens(qtbot, tmp_path):
    _window, setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(response_text()))
    active = setup.read_config().profile
    fetch(qtbot, panel)
    staged = panel.staged_profile

    panel.preview_dialog.reject()  # what Close and Escape do

    assert panel.staged_profile is staged
    assert setup.read_config().profile is active
    assert panel.preview_button.isEnabled()
    assert panel.preview_dialog is None

    panel.preview_button.click()

    assert panel.preview_dialog is not None and panel.preview_dialog.isVisible()
    assert panel.preview_dialog.stats.samples == len(staged.timestamps)


def test_use_profile_logs_at_info_and_opening_the_preview_logs_at_debug(qtbot, tmp_path, caplog):
    _window, _setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(response_text()))

    with caplog.at_level(logging.DEBUG, logger="pvysics"):
        fetch(qtbot, panel)
        panel.preview_dialog.use_button.click()

    opened = [r for r in caplog.records if "preview opened" in r.getMessage()]
    used = [r for r in caplog.records if "Fetched profile used" in r.getMessage()]
    assert opened and opened[0].levelno == logging.DEBUG
    assert used and used[0].levelno == logging.INFO


def test_closing_the_hmi_closes_an_open_preview(qtbot, tmp_path):
    window, _setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(response_text()))
    fetch(qtbot, panel)

    window.close()

    assert panel.preview_dialog is None
    assert panel.staged_profile is not None  # closing the window is not a choice


# Failed fetches never reach the preview

@pytest.mark.parametrize(
    "transport",
    [
        FakeTransport(error=urllib.error.URLError("offline")),
        FakeTransport('{"messages": ["Service is busy"]}', status=503),
        FakeTransport(response_text(rows=["2025,1,15,7,-999,25.0"] + bundled_rows()[1:])),
    ],
    ids=["offline", "http-error", "bad-data"],
)
def test_a_fetch_that_fails_or_is_invalid_never_opens_the_preview(qtbot, tmp_path, transport):
    _window, setup, panel = window_and_panel(qtbot, tmp_path, transport)

    fetch(qtbot, panel)

    assert panel.preview_dialog is None
    assert panel.staged_profile is None
    assert not panel.preview_button.isEnabled()
    assert "Fetch failed" in setup.message


def test_rejected_options_never_open_the_preview(qtbot, tmp_path):
    _window, _setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(response_text()))
    set_range(panel, date(2025, 1, 17), date(2025, 1, 15))

    fetch(qtbot, panel)

    assert panel.preview_dialog is None
    assert panel.staged_profile is None


# A 31-day range

def test_a_31_day_staged_profile_previews_with_a_bounded_number_of_drawn_points(qtbot, tmp_path):
    _window, _setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(thirty_one_day_text()))
    set_range(panel, date(2025, 1, 1), date(2025, 1, 31))

    fetch(qtbot, panel)

    dialog = panel.preview_dialog
    assert dialog is not None
    drawn = len(dialog.irradiance_curve.getData()[0])
    assert drawn == 744 and drawn <= MAX_PLOT_POINTS
    assert len(dialog.temperature_curve.getData()[0]) == drawn
    assert dialog.stats.samples == 744
    assert dialog.stats.days == 31
    assert len(dialog.stats.daily_peak_g) == 31
    assert "Daily peak G" in label_text(dialog)


# Smoke: fake fetch, preview, use, apply, start

def test_smoke_fetch_preview_use_apply_and_start_runs_the_fetched_profile(qtbot, tmp_path):
    window, setup, panel = window_and_panel(qtbot, tmp_path, FakeTransport(bundled_at_33_degrees()))
    fetch(qtbot, panel)
    assert panel.preview_dialog is not None

    panel.preview_dialog.use_button.click()
    setup.apply_button.click()
    window.process_view.start_button.click()
    qtbot.waitUntil(lambda: window.history.sample_count > 0, timeout=WAIT_MS)

    assert window.playback.config.profile is panel.staged_profile
    assert window.playback.is_running
    assert window.history.samples_from(0)[0].true_temperature == pytest.approx(33.3)
    window.playback.pause()
