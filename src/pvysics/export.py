"""CSV export of Samples and of a validation report. Headless, no Qt.

Each writer takes the file path the user chose. Files are UTF-8 and opened with newline="",
so the csv module writes its own line endings on every platform. Blank cells mean no value.
"""

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from pvysics.dataset import DatasetReport
from pvysics.run import Sample, State
from pvysics.validation import STATE_ORDER, ValidationReport

SAMPLE_COLUMNS = (
    "run",
    "timestamp",
    "true_irradiance_w_m2",
    "true_temperature_c",
    "measured_irradiance_w_m2",
    "measured_temperature_c",
    "measured_voltage_v",
    "measured_current_a",
    "power_measured_w",
    "power_predicted_w",
    "deviation_pct",
    "state",
    "active_faults",
)
DATASET_COLUMNS = (
    "timestamp",
    "irradiance_w_m2",
    "temperature_c",
    "voltage_v",
    "current_a",
    "actual_power_w",
    "estimated_power_w",
    "deviation_pct",
    "state",
)
REPORT_COLUMNS = ("section", "measure", "value", "unit")


def write_samples_csv(path: Path, runs: Mapping[str, Sequence[Sample]]) -> None:
    """Every field of every Sample, one row per Sample. The run label says which run it came from."""
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(SAMPLE_COLUMNS)
        for label, samples in runs.items():
            for sample in samples:
                writer.writerow(_sample_row(label, sample))


def write_validation_csv(path: Path, report: ValidationReport) -> None:
    """The error metrics, confusion matrix, detection scores and false-alarm rates of a report."""
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(REPORT_COLUMNS)
        writer.writerows(_report_rows(report))


def write_dataset_analysis_csv(path: Path, report: DatasetReport) -> None:
    """Every analysed row of a dataset (the twin's estimate next to the actual power),
    then the dataset's metrics, in one file."""
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(DATASET_COLUMNS)
        for sample in report.samples:
            writer.writerow(_dataset_row(sample))
        writer.writerow([])
        writer.writerow(REPORT_COLUMNS)
        writer.writerows(_dataset_metric_rows(report))


def _dataset_row(sample: Sample) -> list[str | float]:
    return [
        np.datetime_as_string(sample.timestamp, unit="s"),
        sample.measured_irradiance,
        sample.measured_temperature,
        sample.measured_voltage,
        sample.measured_current,
        sample.power_measured,
        sample.power_predicted,
        sample.deviation_pct,
        sample.state.value,
    ]


def _dataset_metric_rows(report: DatasetReport) -> list[list[str | float | int]]:
    """The dataset's metrics as section/measure/value/unit rows, as write_validation_csv writes them."""
    metrics = report.metrics
    rows: list[list[str | float | int]] = [
        ["summary", "dataset", report.name, ""],
        [
            "summary",
            "daylight rows analysed",
            metrics.sample_count,
            f"of {metrics.row_count} rows (night rows excluded)",
        ],
        ["metrics", "mean G", metrics.mean_irradiance_w_m2, "W/m^2"],
        ["metrics", "mean actual P", metrics.mean_actual_w, "W"],
        ["metrics", "mean estimated P", metrics.mean_estimated_w, "W"],
        ["metrics", "MAE", metrics.mae_w, "W"],
        ["metrics", "RMSE", metrics.rmse_w, "W"],
        ["metrics", "MAPE", metrics.mape_pct, "%"],
        ["metrics", "MBE", metrics.mbe_w, "W"],
        ["metrics", "mean deviation", metrics.mean_deviation_pct, "%"],
    ]
    for state, share in (
        (State.NORMAL, metrics.normal_pct),
        (State.WARNING, metrics.warning_pct),
        (State.ABNORMAL, metrics.abnormal_pct),
    ):
        rows.append(["shares", f"{state.value} share", share, "%"])
    return rows


def _sample_row(label: str, sample: Sample) -> list[str | float]:
    return [
        label,
        np.datetime_as_string(sample.timestamp, unit="s"),
        sample.true_irradiance,
        sample.true_temperature,
        sample.measured_irradiance,
        sample.measured_temperature,
        sample.measured_voltage,
        sample.measured_current,
        sample.power_measured,
        sample.power_predicted,
        sample.deviation_pct,
        sample.state.value,
        "; ".join(kind.value for kind in sample.active_faults),
    ]


def _report_rows(report: ValidationReport) -> list[list[str | float | int]]:
    metrics = report.metrics
    rows: list[list[str | float | int]] = [
        ["metrics", "MAE", metrics.mae_w, "W"],
        ["metrics", "RMSE", metrics.rmse_w, "W"],
        ["metrics", "MAPE", metrics.mape_pct, "%"],
        ["metrics", "daylight samples used for MAE and RMSE", metrics.sample_count, "samples"],
        ["metrics", "daylight samples used for MAPE", metrics.mape_sample_count, "samples"],
    ]
    for state in STATE_ORDER:
        rows.append(
            [
                "confusion",
                f"Normal operation estimated {state.value}",
                report.confusion.count(False, state),
                "samples",
            ]
        )
    for state in STATE_ORDER:
        rows.append(
            ["confusion", f"Fault estimated {state.value}", report.confusion.count(True, state), "samples"]
        )
    for score in report.faults:
        rows.append(["fault", f"{score.kind.value} detection delay", _cell(score.delay_s), "s"])
        rows.append(["fault", f"{score.kind.value} detection rate", _cell(_percent(score.detection_rate)), "%"])
    thresholds, derived = report.config.thresholds, report.derived_thresholds
    rows += [
        ["summary", "mean detection delay", _cell(report.mean_delay_s), "s"],
        ["summary", "detection rate", _cell(_percent(report.detection_rate)), "%"],
        ["summary", "warning limit at config thresholds", thresholds.warning_pct, "%"],
        ["summary", "abnormal limit at config thresholds", thresholds.abnormal_pct, "%"],
        ["summary", "false-alarm rate at config thresholds", report.false_alarm_rate * 100.0, "%"],
        ["summary", "warning limit at derived thresholds", derived.warning_pct, "%"],
        ["summary", "abnormal limit at derived thresholds", derived.abnormal_pct, "%"],
        ["summary", "false-alarm rate at derived thresholds", report.false_alarm_rate_derived * 100.0, "%"],
    ]
    return rows


def _percent(fraction: float | None) -> float | None:
    return None if fraction is None else fraction * 100.0


def _cell(value: float | None) -> float | str:
    return "" if value is None else value
