import csv
from dataclasses import replace

import numpy as np

from pvysics.export import REPORT_COLUMNS, SAMPLE_COLUMNS, write_samples_csv, write_validation_csv
from pvysics.faults import FaultKind, ScheduledFault, default_fault
from pvysics.run import Thresholds, bundled_run_config, run
from pvysics.validation import run_validation

COARSE_STEP_S = 600.0


def coarse_config():
    return replace(bundled_run_config(seed=1), time_step_s=COARSE_STEP_S)


def read_rows(path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def user_folder(tmp_path):
    """A folder whose name has spaces, as a user's folder often does on each platform."""
    folder = tmp_path / "My Validation Reports"
    folder.mkdir()
    return folder


def test_samples_csv_has_every_sample_field_and_one_row_per_sample(tmp_path):
    result = run(coarse_config())
    path = user_folder(tmp_path) / "samples run 1.csv"

    write_samples_csv(path, {"healthy": result.samples})

    rows = read_rows(path)
    assert rows[0] == list(SAMPLE_COLUMNS)
    assert len(rows) == 1 + len(result.samples)
    assert {row[0] for row in rows[1:]} == {"healthy"}


def test_samples_csv_round_trips_the_measured_and_predicted_power_exactly(tmp_path):
    result = run(coarse_config())
    path = tmp_path / "samples.csv"

    write_samples_csv(path, {"healthy": result.samples})

    rows = read_rows(path)[1:]
    columns = {name: index for index, name in enumerate(SAMPLE_COLUMNS)}
    for sample, row in zip(result.samples, rows, strict=True):
        assert float(row[columns["power_measured_w"]]) == sample.power_measured
        assert float(row[columns["power_predicted_w"]]) == sample.power_predicted
        assert row[columns["state"]] == sample.state.value
        assert row[columns["timestamp"]] == np.datetime_as_string(sample.timestamp, unit="s")


def test_samples_csv_names_the_active_faults_of_each_sample(tmp_path):
    soiling = ScheduledFault(default_fault(FaultKind.SOILING), np.datetime64("2025-01-15T10:00:00"))
    faulted = run(replace(coarse_config(), faults=(soiling,)))
    path = tmp_path / "faults.csv"

    write_samples_csv(path, {"soiling": faulted.samples})

    column = SAMPLE_COLUMNS.index("active_faults")
    rows = read_rows(path)[1:]
    assert {row[column] for row in rows} == {"", "soiling"}


def test_samples_csv_uses_crlf_line_endings_without_doubling_them(tmp_path):
    result = run(coarse_config())
    path = tmp_path / "newlines.csv"

    write_samples_csv(path, {"healthy": result.samples})

    data = path.read_bytes()
    assert b"\r\r" not in data
    assert data.count(b"\r\n") == 1 + len(result.samples)


def test_validation_csv_writes_the_metrics_and_scores_to_a_folder_with_spaces(tmp_path):
    report = run_validation(coarse_config())
    path = user_folder(tmp_path) / "metrics report.csv"

    write_validation_csv(path, report)

    rows = read_rows(path)
    assert rows[0] == list(REPORT_COLUMNS)
    values = {(row[0], row[1]): row[2] for row in rows[1:]}
    assert float(values[("metrics", "MAE")]) == report.metrics.mae_w
    assert float(values[("metrics", "RMSE")]) == report.metrics.rmse_w
    assert float(values[("metrics", "MAPE")]) == report.metrics.mape_pct
    assert float(values[("summary", "false-alarm rate at config thresholds")]) == 0.0
    derived = report.derived_thresholds
    assert float(values[("summary", "warning limit at derived thresholds")]) == derived.warning_pct
    assert float(values[("summary", "false-alarm rate at derived thresholds")]) == (
        report.false_alarm_rate_derived * 100.0
    )
    for score in report.faults:
        assert values[("fault", f"{score.kind.value} detection delay")] == str(score.delay_s)


def test_undetected_faults_leave_their_delay_cells_blank(tmp_path):
    report = run_validation(
        replace(coarse_config(), thresholds=Thresholds(warning_pct=150.0, abnormal_pct=199.0))
    )
    path = tmp_path / "undetected.csv"

    write_validation_csv(path, report)

    values = {(row[0], row[1]): row[2] for row in read_rows(path)[1:]}
    assert values[("summary", "mean detection delay")] == ""
    assert values[("fault", "soiling detection delay")] == ""
