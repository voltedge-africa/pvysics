import csv
import threading
from dataclasses import replace

import pytest
from PyQt6.QtWidgets import QFileDialog

from pvysics.export import SAMPLE_COLUMNS
from pvysics.faults import FaultKind
from pvysics.gui import validation_view
from pvysics.gui.main_window import MainWindow
from pvysics.gui.playback import SPEEDS
from pvysics.gui.process_view import PLACEHOLDER
from pvysics.profile import Profile
from pvysics.run import RunConfig, State, Thresholds, bundled_run_config
from pvysics.validation import run_validation
from dataclasses import replace as dc_replace
from pvysics.gui.session import Session

FASTEST = SPEEDS[-1]
WAIT_MS = 120_000
COARSE_STEP_S = 600.0


def coarse_config(**changes) -> RunConfig:
    """The bundled day at a 10-minute step, so a batch takes well under a second."""
    config = replace(bundled_run_config(seed=1), time_step_s=COARSE_STEP_S, **changes)
    profile = config.profile
    cut = Profile(
        timestamps=profile.timestamps[6:20],
        irradiance=profile.irradiance[6:20],
        temperature=profile.temperature[6:20],
        name=profile.name,
    )
    return replace(config, profile=cut)


def validation_of(window: MainWindow):
    return window.open_dashboard().validation


def wait_until_idle(qtbot, view) -> None:
    qtbot.waitUntil(lambda: not view.is_running, timeout=WAIT_MS)


def read_rows(path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


@pytest.fixture
def window(qtbot):
    window = Session(config=coarse_config()).open_hmi()
    qtbot.addWidget(window)
    window.playback.set_speed(FASTEST)
    return window


def test_validation_tab_says_night_is_excluded_and_shows_no_numbers_before_a_run(qtbot, window):
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation

    assert "Night-time samples are excluded" in view.note_label.text()
    assert "MAPE also skips" in view.note_label.text()
    assert view.tiles["mape"].text() == PLACEHOLDER
    assert not view.export_samples_button.isEnabled()
    assert not view.export_metrics_button.isEnabled()


def test_run_validation_runs_off_the_ui_thread_and_disables_the_button_while_it_runs(
    qtbot, window, monkeypatch
):
    threads = []
    original = validation_view.run_validation

    def recording(config):
        threads.append(threading.get_ident())
        return original(config)

    monkeypatch.setattr(validation_view, "run_validation", recording)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation

    view.run_button.click()

    assert not view.run_button.isEnabled()
    assert not view.progress.isHidden()
    wait_until_idle(qtbot, view)
    assert threads and threads[0] != threading.get_ident()
    assert view.run_button.isEnabled()
    assert view.progress.isHidden()
    assert view.report is not None
    assert view.tiles["mae"].text().endswith(" W")


def test_results_are_shown_as_metric_tiles_confusion_matrix_detection_and_false_alarms(qtbot, window):
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation

    view.run_button.click()
    wait_until_idle(qtbot, view)
    report = view.report

    assert view.tiles["rmse"].text() == f"{report.metrics.rmse_w:.2f} W"
    assert view.tiles["mape"].text() == f"{report.metrics.mape_pct:.2f} %"
    assert view.confusion_table.item(1, 2).text() == str(report.confusion.count(True, State.ABNORMAL))
    assert view.fault_table.rowCount() == len(FaultKind)
    assert view.fault_table.item(0, 0).text() == FaultKind.PARTIAL_SHADING.value
    assert view.false_alarm_config_label.text().startswith(f"{report.false_alarm_rate * 100:.1f} %")
    assert f"{report.false_alarm_rate_derived * 100:.1f} %" in view.false_alarm_derived_label.text()
    assert view.export_samples_button.isEnabled() and view.export_metrics_button.isEnabled()


def test_the_applied_setup_is_the_config_that_gets_validated(qtbot, window):
    applied = coarse_config(
        seed=7,
        thresholds=Thresholds(warning_pct=3.0, abnormal_pct=8.0),
        mismatch=replace(bundled_run_config().mismatch, series_resistance_pct=9.0),
    )
    window.setup_view.apply_requested.emit(applied)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation

    view.run_button.click()
    wait_until_idle(qtbot, view)

    assert view.report.config is applied
    assert view.report.config.thresholds == Thresholds(warning_pct=3.0, abnormal_pct=8.0)
    assert "warning 3.00 %, abnormal 8.00 %" in view.config_label.text()


def test_a_result_for_an_older_config_is_marked_stale_after_apply(qtbot, window):
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation
    view.run_button.click()
    wait_until_idle(qtbot, view)

    window.setup_view.apply_requested.emit(coarse_config(seed=5))

    assert "Run validation again" in view.status_label.text()


def test_validation_does_not_change_or_restart_the_live_run(qtbot, window):
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation
    window.process_view.start_button.click()
    for _ in range(3):
        window.playback.tick()
    first_stamp = window.history.samples_from(0)[0].timestamp
    samples_before = window.history.sample_count

    view.run_button.click()
    wait_until_idle(qtbot, view)

    assert window.playback.is_running  # the run keeps playing while the batch runs
    assert window.history.samples_from(0)[0].timestamp == first_stamp  # not restarted
    assert window.history.sample_count >= samples_before


def test_a_failed_validation_is_reported_on_screen_and_the_button_comes_back(qtbot, window, monkeypatch):
    def failing(config):
        raise ValueError("boom in the batch")

    monkeypatch.setattr(validation_view, "run_validation", failing)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation

    view.run_button.click()
    wait_until_idle(qtbot, view)

    assert "boom in the batch" in view.status_label.text()
    assert view.run_button.isEnabled()
    assert view.report is None


def test_export_buttons_write_samples_and_metrics_to_the_files_the_user_chose(qtbot, window, monkeypatch, tmp_path):
    folder = tmp_path / "Validation Output"
    folder.mkdir()
    chosen = iter([str(folder / "day samples"), str(folder / "day metrics.csv")])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (next(chosen), ""))
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation
    view.run_button.click()
    wait_until_idle(qtbot, view)

    view.export_samples_button.click()
    view.export_metrics_button.click()

    samples = folder / "day samples.csv"  # a missing extension is added
    rows = read_rows(samples)
    assert rows[0] == list(SAMPLE_COLUMNS)
    assert len(rows) == 1 + sum(len(run_result.samples) for run_result in _runs(view))
    metrics = read_rows(folder / "day metrics.csv")
    values = {(row[0], row[1]): row[2] for row in metrics[1:]}
    assert float(values[("metrics", "MAE")]) == view.report.metrics.mae_w


def test_cancelling_the_export_dialog_writes_nothing(qtbot, window, monkeypatch, tmp_path):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: ("", ""))
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation
    view.run_button.click()
    wait_until_idle(qtbot, view)

    view.export_metrics_button.click()

    assert list(tmp_path.iterdir()) == []


def test_closing_the_dashboard_during_a_validation_waits_for_it(qtbot, window):
    dashboard = window.open_dashboard()
    view = dashboard.validation
    view.run_button.click()

    dashboard.close()

    assert not view.is_running
    assert not dashboard.isVisible()


def test_the_bundled_day_validation_shows_the_numbers_on_the_tab(qtbot):
    window = Session(config=bundled_run_config(seed=0)).open_hmi()
    qtbot.addWidget(window)
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation

    view.run_button.click()
    wait_until_idle(qtbot, view)

    expected = run_validation(bundled_run_config(seed=0))
    assert view.report.metrics == expected.metrics
    assert view.tiles["mae"].text() == f"{expected.metrics.mae_w:.2f} W"
    assert view.mean_delay_label.text() == "0 s"
    assert view.detection_rate_label.text() == "100.0 %"
    assert view.false_alarm_config_label.text().startswith("0.0 %")


def _runs(view):
    report = view.report
    return [report.healthy] + [fault_run.result for fault_run in report.fault_runs]


def run_and_wait(qtbot, window):
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation
    view.run_button.click()
    wait_until_idle(qtbot, view)
    return view


def test_the_empty_state_shows_until_the_first_report_and_the_results_after(qtbot, window):
    dashboard = window.open_dashboard()
    qtbot.addWidget(dashboard)
    view = dashboard.validation
    dashboard.show()
    dashboard.centralWidget().setCurrentWidget(view)  # a widget is only visible on the tab that is showing

    assert view.empty_label.isVisible() and not view.results.isVisible()

    view.run_button.click()
    wait_until_idle(qtbot, view)

    assert view.results.isVisible() and not view.empty_label.isVisible()


def test_each_fault_shows_a_detected_or_missed_result(qtbot, window):
    view = run_and_wait(qtbot, window)

    for row, score in enumerate(view.report.faults):
        expected = "Detected" if score.delay_s is not None else "Missed"
        assert view.fault_table.item(row, 1).text() == expected





def test_the_confusion_matrix_is_green_where_the_twin_was_right_and_red_where_it_was_wrong():
    right_normal = validation_view._confusion_tint(is_fault=False, state=State.NORMAL, count=5)
    wrong_normal = validation_view._confusion_tint(is_fault=False, state=State.ABNORMAL, count=2)
    right_fault = validation_view._confusion_tint(is_fault=True, state=State.ABNORMAL, count=7)
    missed_fault = validation_view._confusion_tint(is_fault=True, state=State.NORMAL, count=3)

    assert right_normal.green() > right_normal.red() and right_fault.green() > right_fault.red()
    assert wrong_normal.red() > wrong_normal.green() and missed_fault.red() > missed_fault.green()
    assert validation_view._confusion_tint(is_fault=True, state=State.NORMAL, count=0) is None
