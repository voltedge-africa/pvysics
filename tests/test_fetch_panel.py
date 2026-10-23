"""The Fetch profile group on the Setup tab, with fake transports. No test here touches the network."""

import logging
import threading
import urllib.error
from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest
from PyQt6.QtCore import QDate, QTimer
from pvysics.fetch import ProfileFetcher, Response
from pvysics.gui.fetch_panel import FetchPanel, default_cache_dir
from pvysics.gui.session import Session
from pvysics.run import bundled_run_config
from test_fetch import FakeTransport, bundled_rows, response_text

WAIT_MS = 10000
FAKE_SITE = (-33.92, 18.42)  # Cape Town: a site the Setup view is set to in some tests


def window_with(qtbot, config=None):
    window = Session(config=config or bundled_run_config()).open_hmi()
    qtbot.addWidget(window)
    return window


def panel_with(qtbot, transport, tmp_path) -> tuple[object, FetchPanel]:
    """A window whose fetch panel uses the fake transport and a temporary cache directory."""
    window = window_with(qtbot)
    setup = window.setup_view
    setup.fetch_panel.set_fetcher(ProfileFetcher(transport, tmp_path))
    return setup, setup.fetch_panel


def finish(qtbot, panel: FetchPanel) -> None:
    qtbot.waitUntil(lambda: not panel.is_running, timeout=WAIT_MS)


def close_preview(panel: FetchPanel) -> None:
    """Close the preview the way a user does, without choosing: the profile stays staged."""
    panel.preview_dialog.close()


def set_end_date(panel: FetchPanel, day: date) -> None:
    panel.end_edit.setDate(QDate(day.year, day.month, day.day))


def set_start_date(panel: FetchPanel, day: date) -> None:
    panel.start_edit.setDate(QDate(day.year, day.month, day.day))


def test_fetch_group_defaults_to_the_site_location_three_days_and_all_sky(qtbot):
    setup = window_with(qtbot).setup_view
    panel = setup.fetch_panel

    assert panel.use_site_check.isChecked()
    assert panel.latitude_spin.value() == pytest.approx(-29.85)
    assert panel.longitude_spin.value() == pytest.approx(31.00)
    assert not panel.latitude_spin.isEnabled()
    assert panel.irradiance_box.currentText() == "All-sky"
    assert panel.standard_box.currentText() == "Local standard time (LST)"
    options = panel.options()
    assert (options.end - options.start).days == 2
    assert options.end < date.today()
    assert panel.staged_profile is None
    assert not panel.preview_button.isEnabled()


def test_unchecking_use_site_location_enables_its_own_fields(qtbot):
    panel = window_with(qtbot).setup_view.fetch_panel

    panel.use_site_check.setChecked(False)
    panel.latitude_spin.setValue(-1.5)
    panel.longitude_spin.setValue(36.8)

    assert panel.latitude_spin.isEnabled()
    assert panel.options().latitude == pytest.approx(-1.5)
    assert panel.options().longitude == pytest.approx(36.8)


def test_site_fields_in_the_setup_tab_are_followed_while_use_site_location_is_checked(qtbot):
    setup = window_with(qtbot).setup_view

    setup.latitude_spin.setValue(FAKE_SITE[0])
    setup.longitude_spin.setValue(FAKE_SITE[1])

    assert setup.fetch_panel.options().latitude == pytest.approx(FAKE_SITE[0])
    assert setup.fetch_panel.options().longitude == pytest.approx(FAKE_SITE[1])


def test_fetch_asks_for_clear_sky_when_clear_sky_is_chosen(qtbot, tmp_path):
    transport = FakeTransport(response_text("CLRSKY_SFC_SW_DWN"))
    setup, panel = panel_with(qtbot, transport, tmp_path)
    panel.irradiance_box.setCurrentIndex(1)

    panel.start_fetch()
    finish(qtbot, panel)

    params = parse_qs(urlparse(transport.urls[0]).query)
    assert params["parameters"] == ["CLRSKY_SFC_SW_DWN,T2M"]


def test_fetch_asks_for_utc_and_the_chosen_dates_when_set(qtbot, tmp_path):
    transport = FakeTransport(response_text())
    setup, panel = panel_with(qtbot, transport, tmp_path)
    panel.standard_box.setCurrentIndex(1)
    set_start_date(panel, date(2025, 1, 15))
    set_end_date(panel, date(2025, 1, 16))

    panel.start_fetch()
    finish(qtbot, panel)

    params = parse_qs(urlparse(transport.urls[0]).query)
    assert params["time-standard"] == ["UTC"]
    assert params["start"] == ["20250115"]
    assert params["end"] == ["20250116"]


def test_a_fetch_is_staged_with_a_summary_and_does_not_change_the_active_profile(qtbot, tmp_path):
    transport = FakeTransport(response_text())
    setup, panel = panel_with(qtbot, transport, tmp_path)
    active = setup.profile_name

    panel.start_fetch()
    finish(qtbot, panel)

    assert panel.staged_profile is not None
    assert setup.profile_name == active
    assert panel.preview_button.isEnabled()
    summary = panel.status_label.text()
    assert "72 samples" in summary
    assert "from the network" in summary
    assert "2025-01-15 00:00" in summary and "2025-01-17 23:00" in summary


def test_use_profile_in_the_preview_makes_the_fetched_profile_active_and_it_shows_in_the_run_summary(qtbot, tmp_path):
    transport = FakeTransport(response_text())
    setup, panel = panel_with(qtbot, transport, tmp_path)
    panel.start_fetch()
    finish(qtbot, panel)
    staged_name = panel.staged_profile.name

    panel.preview_dialog.use_button.click()

    assert setup.profile_name == staged_name
    assert "NASA POWER" in setup.read_config().profile.name
    assert staged_name in setup.summary_label.text()
    assert "Apply and start" in setup.message
    assert setup.profile_box.findData(staged_name) >= 0
    assert panel.preview_dialog is None


def test_a_repeat_fetch_is_served_from_cache_and_the_summary_says_so(qtbot, tmp_path):
    transport = FakeTransport(response_text())
    setup, panel = panel_with(qtbot, transport, tmp_path)
    panel.start_fetch()
    finish(qtbot, panel)

    panel.start_fetch()
    finish(qtbot, panel)

    assert len(transport.urls) == 1
    assert "from cache" in panel.status_label.text()


def test_offline_fetch_shows_a_problem_logs_an_error_and_keeps_the_active_profile(qtbot, tmp_path, caplog):
    transport = FakeTransport(error=urllib.error.URLError("no route to host"))
    setup, panel = panel_with(qtbot, transport, tmp_path)
    active = setup.profile_name

    with caplog.at_level(logging.ERROR, logger="pvysics"):
        panel.start_fetch()
        finish(qtbot, panel)

    assert setup.profile_name == active
    assert panel.staged_profile is None
    assert "Fetch failed" in setup.message
    assert "could not reach NASA POWER" in setup.message
    assert "active profile is unchanged" in setup.message
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_http_error_is_shown_with_its_code_and_message(qtbot, tmp_path):
    transport = FakeTransport('{"messages": ["Service is busy"]}', status=503)
    setup, panel = panel_with(qtbot, transport, tmp_path)

    panel.start_fetch()
    finish(qtbot, panel)

    assert "HTTP 503: Service is busy" in setup.message


def test_a_previous_staged_profile_survives_a_failed_fetch(qtbot, tmp_path):
    transport = FakeTransport(response_text())
    setup, panel = panel_with(qtbot, transport, tmp_path)
    panel.start_fetch()
    finish(qtbot, panel)
    staged = panel.staged_profile

    close_preview(panel)
    transport.error = urllib.error.URLError("offline now")
    set_start_date(panel, date(2025, 1, 10))
    set_end_date(panel, date(2025, 1, 12))
    panel.start_fetch()
    finish(qtbot, panel)

    assert panel.staged_profile is staged
    assert panel.preview_button.isEnabled()


def test_rejected_options_are_a_warning_and_make_no_request(qtbot, tmp_path, caplog):
    transport = FakeTransport(response_text())
    setup, panel = panel_with(qtbot, transport, tmp_path)
    set_start_date(panel, date(2025, 1, 17))
    set_end_date(panel, date(2025, 1, 15))

    with caplog.at_level(logging.WARNING, logger="pvysics"):
        panel.start_fetch()
        finish(qtbot, panel)

    assert transport.urls == []
    assert "is before the start date" in setup.message
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_bad_data_is_a_warning_naming_the_missing_value(qtbot, tmp_path):
    rows = bundled_rows()
    rows[7] = "2025,1,15,7,-999,25.0"
    setup, panel = panel_with(qtbot, FakeTransport(response_text(rows=rows)), tmp_path)

    panel.start_fetch()
    finish(qtbot, panel)

    assert "-999" in setup.message
    assert panel.staged_profile is None


def test_fetch_runs_off_the_ui_thread_and_the_window_stays_responsive(qtbot, tmp_path):
    release = threading.Event()
    seen_threads = []

    class SlowTransport:
        def __call__(self, url):
            seen_threads.append(threading.get_ident())
            release.wait(5.0)
            return Response(200, response_text())

    setup, panel = panel_with(qtbot, SlowTransport(), tmp_path)
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(10)
    panel.start_fetch()

    qtbot.waitUntil(lambda: len(ticks) >= 5, timeout=WAIT_MS)  # the event loop keeps running during the fetch

    assert panel.is_running
    assert not panel.fetch_button.isEnabled()
    assert panel.cancel_button.isEnabled()
    assert not panel.progress.isHidden()
    assert not panel.use_site_check.isEnabled()
    assert setup.validate_button.isEnabled()  # the rest of the window is not blocked
    assert seen_threads and seen_threads[0] != threading.get_ident()
    release.set()
    timer.stop()
    finish(qtbot, panel)
    assert panel.fetch_button.isEnabled()
    assert not panel.cancel_button.isEnabled()


def test_cancel_discards_the_result_and_leaves_the_active_profile(qtbot, tmp_path):
    release = threading.Event()

    class SlowTransport:
        def __call__(self, url):
            release.wait(5.0)
            return Response(200, response_text())

    setup, panel = panel_with(qtbot, SlowTransport(), tmp_path)
    active = setup.profile_name
    panel.start_fetch()

    panel.cancel_button.click()
    release.set()
    finish(qtbot, panel)

    assert panel.staged_profile is None
    assert setup.profile_name == active
    assert "Fetch cancelled" in setup.message
    assert not panel.preview_button.isEnabled()


def test_shutdown_ends_a_running_fetch_before_the_window_closes(qtbot, tmp_path):
    release = threading.Event()

    class SlowTransport:
        def __call__(self, url):
            release.wait(5.0)
            return Response(200, response_text())

    setup, panel = panel_with(qtbot, SlowTransport(), tmp_path)
    panel.start_fetch()
    release.set()

    setup.shutdown()

    assert not panel.is_running


def test_controls_are_disabled_while_a_fetch_runs(qtbot, tmp_path):
    release = threading.Event()

    class SlowTransport:
        def __call__(self, url):
            release.wait(5.0)
            return Response(200, response_text())

    setup, panel = panel_with(qtbot, SlowTransport(), tmp_path)
    panel.start_fetch()

    assert not panel.use_site_check.isEnabled()
    assert not panel.start_edit.isEnabled()
    assert not panel.irradiance_box.isEnabled()
    release.set()
    finish(qtbot, panel)
    assert panel.start_edit.isEnabled()


def test_the_fetch_cache_is_in_the_platform_cache_location_under_a_profiles_folder(qtbot):
    cache = default_cache_dir()

    assert cache.name == "profiles"
    assert cache.is_absolute()


def test_fetch_group_is_part_of_the_setup_tab_and_its_buttons_are_named(qtbot):
    window = window_with(qtbot)
    panel = window.setup_view.fetch_panel

    assert panel.title() == "Fetch profile (NASA POWER)"
    assert [button.text() for button in (panel.fetch_button, panel.cancel_button, panel.preview_button)] == [
        "Fetch",
        "Cancel",
        "Preview...",
    ]


def test_a_failed_fetch_is_one_error_line_in_the_log_pane(qtbot, tmp_path):
    window = window_with(qtbot)
    window.show()
    qtbot.waitExposed(window)
    panel = window.setup_view.fetch_panel
    panel.set_fetcher(ProfileFetcher(FakeTransport(error=urllib.error.URLError("offline")), tmp_path))

    panel.start_fetch()
    finish(qtbot, panel)

    text = window.log_pane.text_view.toPlainText
    qtbot.waitUntil(lambda: "Fetch failed" in text(), timeout=WAIT_MS)
    failures = [line for line in text().splitlines() if "Fetch failed" in line]
    assert len(failures) == 1
    assert "ERROR" in failures[0]


def test_the_result_is_handled_on_the_ui_thread_not_the_worker_thread(qtbot, tmp_path):
    handled_on = []
    setup, panel = panel_with(qtbot, FakeTransport(response_text()), tmp_path)
    original = panel._on_succeeded

    def spy(result):
        handled_on.append(threading.get_ident())
        original(result)

    panel._on_succeeded = spy  # the connection is made in start_fetch, so it uses this attribute
    panel.start_fetch()
    finish(qtbot, panel)

    assert handled_on == [threading.main_thread().ident]
    assert panel.staged_profile is not None
