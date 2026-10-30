"""The live feed in the app: a device's POST through a real socket onto the Dashboard. Headless Qt."""

import json
import socket
import urllib.error
import urllib.request

import pytest

from pvysics.gui.live_controller import FeedStatus
from pvysics.gui.session import Session
from pvysics.live import LIVE_DIR_ENV
from pvysics.run import bundled_run_config
from pvysics.single_diode import solve_curve

CONFIG = bundled_run_config(seed=0)


@pytest.fixture
def app(qtbot, tmp_path, monkeypatch):
    """A session with the simple window open, the live log in a temporary folder and the feed on a free port."""
    monkeypatch.setenv(LIVE_DIR_ENV, str(tmp_path / "live"))
    session = Session()
    window = session.open_simple()
    qtbot.addWidget(window)
    session.live.configure(0, 5, False)  # port chosen by the system, this computer only
    window.live_page.port_spin.setValue(0)
    window.live_page.network_check.setChecked(False)
    yield session, window
    session.close()


def reading(stamp: str, g=800.0, t=35.0, drop=1.0) -> dict:
    curve = solve_curve(CONFIG.datasheet, g, t)
    return {"timestamp": stamp, "g": g, "t": t, "v": curve.mpp_voltage, "i": curve.mpp_current * drop}


def post(session, body, token=None) -> tuple[int, dict]:
    live = session.live
    request = urllib.request.Request(
        f"http://127.0.0.1:{live.listening_port}/reading", data=json.dumps(body).encode(), method="POST"
    )
    request.add_header("X-Api-Key", live.token if token is None else token)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def start(window, qtbot):
    window.live_page.start_button.click()
    qtbot.waitUntil(lambda: window.session.live.is_active)


def wait_samples(session, qtbot, count):
    qtbot.waitUntil(lambda: session.history.sample_count == count, timeout=5000)


def test_the_page_starts_and_stops_the_feed(app, qtbot):
    session, window = app

    start(window, qtbot)

    assert session.live.status is FeedStatus.WAITING
    assert window.live_page.stop_button.isEnabled() and not window.live_page.start_button.isEnabled()
    assert window.dashboard_page.source_chip.text() == "●  SOURCE: LIVE FEED"
    assert str(session.live.listening_port) in window.live_page.example_text
    assert session.live.token in window.live_page.example_text

    window.live_page.stop_button.click()

    assert not session.live.is_active and session.live.status is FeedStatus.STOPPED
    assert window.live_page.start_button.isEnabled()
    assert window.dashboard_page.source_chip.text() == "●  SOURCE: LIVE FEED (STOPPED)"


def test_a_posted_reading_reaches_the_dashboard(app, qtbot):
    session, window = app
    start(window, qtbot)

    status, reply = post(session, reading("2025-01-15T10:00:00"))
    wait_samples(session, qtbot, 1)

    assert (status, reply) == (202, {"accepted": 1, "errors": []})
    assert session.live.status is FeedStatus.RECEIVING
    assert window.dashboard_page.state_text == "SYSTEM STATE: NORMAL"
    assert window.live_page.counts_label.text().startswith("1 readings accepted")
    assert "2025-01-15 10:00:00" in window.live_page.last_label.text()


def test_starting_to_send_at_midday_raises_no_alarm(app, qtbot):
    """Nothing came in the morning. The first reading at 13:00 is scored on its own: Normal, and no alarm."""
    session, window = app
    start(window, qtbot)

    post(session, reading("2025-01-15T13:00:00"))
    wait_samples(session, qtbot, 1)

    assert window.dashboard_page.state_text == "SYSTEM STATE: NORMAL"
    assert len(session.alarms.log.alarms) == 0
    assert session.history.event_count == 0


def test_a_faulty_reading_raises_an_alarm_and_an_event(app, qtbot):
    session, window = app
    start(window, qtbot)
    post(session, reading("2025-01-15T10:00:00"))
    post(session, reading("2025-01-15T10:01:00", drop=0.7))
    wait_samples(session, qtbot, 2)

    assert window.dashboard_page.state_text == "SYSTEM STATE: ABNORMAL"
    assert len(session.alarms.log.alarms) == 1
    assert [e.detail for e in session.history.events_from(0) if e.kind == "state"] == ["Normal -> Abnormal"]


def test_readings_with_the_wrong_token_or_out_of_order_change_nothing(app, qtbot):
    session, window = app
    start(window, qtbot)
    post(session, reading("2025-01-15T10:00:00"))
    wait_samples(session, qtbot, 1)

    assert post(session, reading("2025-01-15T10:05:00"), token="wrong")[0] == 401
    status, reply = post(session, reading("2025-01-15T09:00:00"))
    qtbot.waitUntil(lambda: session.live.rejected == 1)

    assert status == 422 and "time does not increase" in reply["errors"][0]
    assert session.history.sample_count == 1
    qtbot.waitUntil(lambda: "time does not increase" in window.live_page.problem_label.text())


def test_silence_shows_no_data_and_the_state_returns_with_the_next_reading(app, qtbot):
    session, window = app
    start(window, qtbot)
    post(session, reading("2025-01-15T10:00:00"))
    wait_samples(session, qtbot, 1)

    session.live.timeout_s = 0  # any silence counts
    session.live._check_silence()

    assert session.live.status is FeedStatus.NO_DATA
    assert window.dashboard_page.state_text == "SYSTEM STATE: NO DATA"
    session.live.timeout_s = 600
    post(session, reading("2025-01-15T10:01:00"))
    qtbot.waitUntil(lambda: session.live.status is FeedStatus.RECEIVING)
    assert window.dashboard_page.state_text == "SYSTEM STATE: NORMAL"


def test_the_run_controls_are_disabled_while_live_and_come_back_after(app, qtbot):
    session, window = app
    toolbar = window.dashboard_page.toolbar
    assert toolbar.speed_box.isEnabled() and toolbar.start_button.isEnabled()

    start(window, qtbot)

    for widget in (toolbar.start_button, toolbar.pause_button, toolbar.reset_button, toolbar.speed_box,
                   toolbar.clear_faults_button, *toolbar.fault_buttons.values()):
        assert not widget.isEnabled()

    window.live_page.stop_button.click()

    assert toolbar.speed_box.isEnabled() and toolbar.start_button.isEnabled()


def test_starting_a_simulated_run_after_a_feed_begins_afresh(app, qtbot):
    session, window = app
    start(window, qtbot)
    post(session, reading("2025-01-15T13:00:00"))
    wait_samples(session, qtbot, 1)
    window.live_page.stop_button.click()
    assert session.live.has_data

    window.dashboard_page.toolbar.start_button.click()

    assert session.playback.is_running
    assert session.history.sample_count == 0 or str(session.history.samples_from(0)[0].timestamp).startswith("2025-01-15T00")
    assert not session.live.has_data


def test_applying_a_setup_replaces_the_feed(app, qtbot):
    session, window = app
    start(window, qtbot)

    session.apply_config(bundled_run_config())

    assert not session.live.is_active


def test_every_accepted_reading_is_kept_in_a_file_that_imports(app, qtbot, tmp_path):
    from pvysics.dataset import read_measurement_file

    session, window = app
    start(window, qtbot)
    post(session, [reading("2025-01-15T10:00:00"), reading("2025-01-15T10:01:00")])
    wait_samples(session, qtbot, 2)
    window.live_page.stop_button.click()

    files = list((tmp_path / "live").glob("live-*.csv"))

    assert len(files) == 1
    assert len(read_measurement_file(files[0]).timestamps) == 2
    assert str(files[0]) in window.live_page.log_label.text()


def test_a_taken_port_is_reported_and_the_feed_stays_stopped(app, qtbot):
    session, window = app
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        taken = blocker.getsockname()[1]
        window.live_page.port_spin.setValue(taken)
        window.live_page.network_check.setChecked(False)

        window.live_page.start_button.click()

        assert not session.live.is_active
        assert "Could not listen" in window.live_page.message_label.text()


def test_the_token_is_kept_between_sessions_and_can_be_replaced(app, qtbot):
    session, window = app
    old = session.live.token

    window.live_page.new_token_button.click()

    assert session.live.token != old and window.live_page.token_edit.text() == session.live.token
    assert len(session.live.token) >= 16
    from pvysics.gui.live_controller import LiveController

    assert LiveController(session.bus, lambda: session.config).token == session.live.token  # a new token is kept at once

    start(window, qtbot)  # the token a feed starts with is kept too

    assert LiveController(session.bus, lambda: session.config).token == session.live.token


def test_opening_the_app_writes_no_settings(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv(LIVE_DIR_ENV, str(tmp_path / "live"))
    session = Session()
    qtbot.addWidget(session.open_simple())

    assert list(tmp_path.glob("**/*.ini")) == []
    session.close()
