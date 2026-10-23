"""The log pane and the log bridge, offscreen: one shared model, bottom docks, filter, clear, copy,
colours from the theme, thread safety, and the key actions that log."""

import logging
import threading
from dataclasses import replace

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

from pvysics.faults import FaultKind
from pvysics.gui import validation_view
from pvysics.gui.palette import CHOICE_DARK, CHOICE_LIGHT, DARK, LIGHT
from pvysics.gui.session import Session
from pvysics.profile import Profile
from pvysics.run import bundled_run_config

LOG = logging.getLogger("pvysics.test")
FASTEST = 28800.0


def midday_config():
    """The bundled day cut to 10:00 to 14:00, so a few ticks and a short validation cover it."""
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


def shown(qtbot, window):
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window


def pane_text(pane) -> str:
    pane.refresh()
    return pane.text_view.toPlainText()


def test_both_windows_show_the_same_log_model(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    dashboard = shown(qtbot, session.open_dashboard())

    LOG.warning("one shared line")

    assert hmi.log_pane.visible_text() == dashboard.log_pane.visible_text()
    assert "one shared line" in pane_text(dashboard.log_pane)
    assert session.log_bridge.model is session.log_model


def test_the_log_pane_docks_at_the_bottom_of_both_windows(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    dashboard = shown(qtbot, session.open_dashboard())

    assert hmi.dockWidgetArea(hmi.log_pane) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert dashboard.dockWidgetArea(dashboard.log_pane) == Qt.DockWidgetArea.BottomDockWidgetArea


def test_the_pane_is_visible_by_default_and_small(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    hmi.resize(900, 700)
    qtbot.wait(50)

    pane = hmi.log_pane
    assert pane.isVisible()
    assert not pane.is_collapsed
    assert pane.height() < hmi.height() / 3


def test_collapsing_hides_the_list_keeps_the_header_and_shrinks_the_dock(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    qtbot.wait(100)  # let the dock take its opening height before it is measured
    pane = hmi.log_pane
    expanded_height = pane.height()

    pane.collapse_button.click()

    assert pane.is_collapsed
    assert not pane.text_view.isVisible()
    assert pane.collapse_button.isVisible()
    qtbot.waitUntil(lambda: pane.height() < expanded_height)
    pane.collapse_button.click()
    assert not pane.is_collapsed
    assert pane.text_view.isVisible()
    qtbot.waitUntil(lambda: pane.height() == expanded_height)


def test_the_hide_button_removes_the_pane_and_the_view_menu_brings_it_back(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    pane = hmi.log_pane
    assert pane.view_action.isChecked()

    pane.hide_button.click()

    assert not pane.isVisible()
    assert not pane.view_action.isChecked()
    pane.view_action.trigger()  # View > Show log
    qtbot.waitUntil(pane.isVisible)  # a dock is shown again through the event loop
    assert pane.view_action.isChecked()


def test_hiding_the_log_does_not_lose_lines_and_each_window_hides_its_own(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    dashboard = shown(qtbot, session.open_dashboard())

    hmi.log_pane.hide_button.click()
    LOG.warning("logged while hidden")
    hmi.log_pane.view_action.trigger()
    qtbot.waitUntil(hmi.log_pane.isVisible)

    assert dashboard.log_pane.isVisible()  # hiding one window's pane leaves the other's alone
    assert "logged while hidden" in pane_text(hmi.log_pane)


def test_show_log_is_in_the_view_menu_of_both_windows_with_a_shortcut(qtbot, session):
    for window in (shown(qtbot, session.open_hmi()), shown(qtbot, session.open_dashboard())):
        view_menu = next(a.menu() for a in window.menuBar().actions() if a.text().replace("&", "") == "View")
        assert window.log_pane.view_action in view_menu.actions()
        assert window.log_pane.view_action.shortcut().toString() == "Ctrl+L"


def test_a_rejected_csv_logs_a_warning_line_with_the_reason(qtbot, session, tmp_path):
    hmi = shown(qtbot, session.open_hmi())
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")

    hmi.setup_view.load_csv(str(empty))

    line = [text for text in pane_text(hmi.log_pane).splitlines() if "empty.csv" in text][0]
    assert "WARNING" in line
    assert "empty.csv: the file has no header row. The profile is unchanged." in line
    assert hmi.log_pane.line_colours()[-1] == session.theme.palette.warning


def test_a_rejected_datasheet_logs_a_warning_line_with_the_reason(qtbot, session, tmp_path):
    hmi = shown(qtbot, session.open_hmi())
    broken = tmp_path / "module.json"
    broken.write_text("{", encoding="utf-8")

    hmi.setup_view.load_datasheet(str(broken))

    text = pane_text(hmi.log_pane)
    assert "WARNING" in text
    assert "Datasheet rejected: module.json: not valid JSON" in text


def test_the_level_filter_hides_lower_lines_without_losing_them(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    pane = hmi.log_pane
    LOG.debug("quiet detail")
    LOG.warning("loud warning")

    assert pane.level_box.currentData() == logging.INFO
    assert "quiet detail" not in pane_text(pane)

    pane.level_box.setCurrentIndex(pane.level_box.findData(logging.WARNING))
    assert "loud warning" in pane_text(pane)
    assert "quiet detail" not in pane_text(pane)

    pane.level_box.setCurrentIndex(pane.level_box.findData(logging.DEBUG))
    assert "quiet detail" in pane_text(pane)
    assert len(session.log_model) >= 2


def test_the_filter_is_shared_by_both_windows(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    dashboard = shown(qtbot, session.open_dashboard())
    LOG.info("ordinary line")

    hmi.log_pane.level_box.setCurrentIndex(hmi.log_pane.level_box.findData(logging.ERROR))

    assert "ordinary line" not in pane_text(dashboard.log_pane)


def test_clear_empties_both_panes(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    dashboard = shown(qtbot, session.open_dashboard())
    LOG.info("to be cleared")

    hmi.log_pane.clear_button.click()

    assert len(session.log_model) == 0
    assert pane_text(hmi.log_pane) == ""
    assert pane_text(dashboard.log_pane) == ""


def test_copy_puts_the_visible_text_on_the_clipboard(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    LOG.debug("hidden by the filter")
    LOG.warning("copied line")

    hmi.log_pane.copy_button.click()

    clipboard = QGuiApplication.clipboard().text()
    assert clipboard == hmi.log_pane.visible_text()
    assert "copied line" in clipboard
    assert "hidden by the filter" not in clipboard


def test_warning_and_error_lines_use_the_palette_and_follow_a_theme_change(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    session.theme.set_choice(CHOICE_LIGHT)
    LOG.info("plain")
    LOG.warning("careful")
    LOG.error("broken")

    pane = hmi.log_pane
    assert pane.line_colours()[-3:] == (None, LIGHT.warning, LIGHT.error)

    session.theme.set_choice(CHOICE_DARK)

    assert pane.line_colours()[-2:] == (DARK.warning, DARK.error)


def test_the_view_follows_the_newest_line_unless_the_user_scrolled_up(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    pane = hmi.log_pane
    for index in range(200):
        LOG.info("filler %d", index)
    pane_text(pane)
    bar = pane.text_view.verticalScrollBar()

    bar.setValue(bar.maximum())
    LOG.info("follows")
    pane.refresh()
    assert bar.value() == bar.maximum()

    bar.setValue(0)
    LOG.info("does not follow")
    pane.refresh()
    assert bar.value() == 0


def test_a_log_call_from_a_worker_thread_reaches_the_pane_through_the_ui_thread(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    worker = threading.Thread(target=LOG.warning, args=("written on a worker thread",))

    worker.start()
    worker.join()

    qtbot.waitUntil(lambda: "written on a worker thread" in hmi.log_pane.text_view.toPlainText())


def test_a_failed_validation_logs_an_error_from_the_worker_thread(qtbot, session, monkeypatch):
    def failing(config):
        raise ValueError("boom in the batch")

    monkeypatch.setattr(validation_view, "run_validation", failing)
    hmi = shown(qtbot, session.open_hmi())
    dashboard = shown(qtbot, session.open_dashboard())
    view = dashboard.validation

    view.run_button.click()
    qtbot.waitUntil(lambda: not view.is_running)

    text = pane_text(hmi.log_pane)
    assert "ERROR" in text
    assert "Validation failed: boom in the batch" in text


def test_validation_export_writes_an_info_or_error_line(qtbot, session, monkeypatch, tmp_path):
    hmi = shown(qtbot, session.open_hmi())
    dashboard = shown(qtbot, session.open_dashboard())
    view = dashboard.validation
    view.run_button.click()
    qtbot.waitUntil(lambda: not view.is_running)
    missing_folder = tmp_path / "missing" / "metrics.csv"
    monkeypatch.setattr(validation_view, "_choose_csv", lambda parent, title: missing_folder)

    view.export_metrics_button.click()
    assert "ERROR" in pane_text(hmi.log_pane)
    assert "could not write metrics.csv" in pane_text(hmi.log_pane)

    good = tmp_path / "metrics.csv"
    monkeypatch.setattr(validation_view, "_choose_csv", lambda parent, title: good)
    view.export_metrics_button.click()
    assert "Metrics exported to" in pane_text(hmi.log_pane)


def test_applying_a_setup_and_injecting_a_fault_log_lines_in_both_windows(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    dashboard = shown(qtbot, session.open_dashboard())

    hmi.setup_view.apply()
    hmi.process_view.fault_buttons[FaultKind.PARTIAL_SHADING].click()

    for window in (hmi, dashboard):
        text = pane_text(window.log_pane)
        assert "Setup applied: profile" in text
        assert "Fault injected: partial shading (severity 0.3)" in text
        assert "Run started" in text


def test_a_state_change_and_an_abnormal_alarm_log_their_levels(qtbot, session):
    hmi = shown(qtbot, session.open_hmi())
    hmi.process_view.start_button.click()
    session.playback.tick()
    hmi.process_view.fault_buttons[FaultKind.PARTIAL_SHADING].click()

    for _ in range(3):
        session.playback.tick()

    text = pane_text(hmi.log_pane)
    assert "State changed: Normal -> Abnormal" in text
    alarm_line = [line for line in text.splitlines() if "Alarm Abnormal" in line][0]
    assert "ERROR" in alarm_line
    assert "probable cause: partial shading" in alarm_line


def test_a_closed_session_detaches_its_log_handler(qtbot):
    logger = logging.getLogger("pvysics")
    before = list(logger.handlers)
    session = Session(config=midday_config())
    assert len(logger.handlers) == len(before) + 1

    session.close()
    session.close()

    assert logger.handlers == before
    LOG.warning("after close")
    assert all("after close" not in entry.message for entry in session.log_model.visible())
