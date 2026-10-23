"""Validation: error metrics, fault-detection scores and the batch that produces them. Headless, no Qt.

Error metrics compare P measured with P predicted over daylight Samples, those with predicted
power at or above POWER_FLOOR_W, so night-time cannot dilute them. MAE and RMSE use every
daylight Sample. MAPE divides by P measured, so it also skips daylight Samples where P measured
is below NEAR_ZERO_W (the same 5 W floor): a percentage of near-zero power says nothing.

Fault scoring runs one labelled fault per FaultKind, at default severity, on the config's
profile, mismatch, sensors, seed and thresholds. Each fault starts at FAULT_START_HOUR on the
first day of the profile and clears FAULT_WINDOW_MINUTES later; the config's own scheduled
faults are replaced. Ground truth per Sample is "fault active", meaning active_faults is not
empty. Detection delay is measured from the fault start to the first fault-active Sample whose
State is not Normal. Detection rate is the fraction of fault-active daylight Samples whose State
is Warning or Abnormal. Rates are fractions from 0 to 1 unless a name says percent.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

import numpy as np

from pvysics.faults import FaultKind, ScheduledFault, default_fault
from pvysics.run import POWER_FLOOR_W, RunConfig, RunResult, Sample, State, Thresholds, run
from pvysics.run_setup import derive_thresholds

FAULT_START_HOUR = 10.0  # mid-morning: daylight on every bundled day
FAULT_WINDOW_MINUTES = 60  # each labelled fault lasts an hour, then clears
NEAR_ZERO_W = POWER_FLOOR_W  # measured power below this is excluded from MAPE
STATE_ORDER = (State.NORMAL, State.WARNING, State.ABNORMAL)


@dataclass(frozen=True)
class ErrorMetrics:
    mae_w: float
    rmse_w: float
    mape_pct: float
    sample_count: int  # daylight Samples used for MAE and RMSE
    mape_sample_count: int  # daylight Samples with P measured at or above NEAR_ZERO_W


@dataclass(frozen=True)
class ConfusionMatrix:
    """Daylight Samples by truth (rows: Normal operation, Fault) and estimated State (columns)."""

    counts: tuple[tuple[int, int, int], tuple[int, int, int]]

    def count(self, fault_active: bool, state: State) -> int:
        return self.counts[int(fault_active)][STATE_ORDER.index(state)]


@dataclass(frozen=True)
class FaultRun:
    kind: FaultKind
    start: np.datetime64
    end: np.datetime64  # the fault is cleared from this time on
    result: RunResult


@dataclass(frozen=True)
class FaultScore:
    kind: FaultKind
    delay_s: float | None  # None when the fault was never detected
    detection_rate: float | None  # None when the fault had no daylight Samples


@dataclass(frozen=True)
class ValidationReport:
    config: RunConfig
    healthy: RunResult  # fault-free run at the config's thresholds
    metrics: ErrorMetrics
    fault_runs: tuple[FaultRun, ...]
    faults: tuple[FaultScore, ...]
    confusion: ConfusionMatrix
    mean_delay_s: float | None  # over the detected faults
    detection_rate: float | None  # over all fault-active daylight Samples
    false_alarm_rate: float  # healthy run at the config's thresholds
    derived_thresholds: Thresholds  # mean + 2 and 3 sigma of the healthy deviation
    false_alarm_rate_derived: float  # healthy run at the derived thresholds


def error_metrics(source: RunResult | Iterable[Sample]) -> ErrorMetrics:
    """MAE, RMSE and MAPE between P measured and P predicted, over daylight Samples."""
    daylight = [sample for sample in _samples(source) if sample.power_predicted >= POWER_FLOOR_W]
    if not daylight:
        raise ValueError("there is no daylight to compare, so no error metrics")
    measured = np.array([sample.power_measured for sample in daylight])
    predicted = np.array([sample.power_predicted for sample in daylight])
    error = measured - predicted
    lit = measured >= NEAR_ZERO_W
    if not lit.any():
        raise ValueError("no daylight Sample has measured power above the near-zero floor")
    relative = np.abs(error[lit]) / measured[lit]
    return ErrorMetrics(
        mae_w=float(np.mean(np.abs(error))),
        rmse_w=float(np.sqrt(np.mean(error**2))),
        mape_pct=float(np.mean(relative) * 100.0),
        sample_count=len(daylight),
        mape_sample_count=int(lit.sum()),
    )


def false_alarm_rate(source: RunResult | Iterable[Sample]) -> float:
    """The fraction of daylight Samples whose State is not Normal. Meant for a fault-free run."""
    daylight = [sample for sample in _samples(source) if sample.power_predicted >= POWER_FLOOR_W]
    if not daylight:
        raise ValueError("there is no daylight, so no false-alarm rate")
    return sum(sample.state is not State.NORMAL for sample in daylight) / len(daylight)


def fault_start(profile) -> np.datetime64:
    """The first Sample at or after FAULT_START_HOUR on the first day of the profile."""
    target = profile.timestamps[0].astype("datetime64[D]") + np.timedelta64(
        round(FAULT_START_HOUR * 60), "m"
    )
    later = profile.timestamps[profile.timestamps >= target]
    if later.size == 0:
        raise ValueError("the profile has no Sample at or after the fault start time")
    return later[0]


def fault_batch(config: RunConfig) -> tuple[FaultRun, ...]:
    """One labelled fault run per FaultKind, each starting at the same time and clearing after the window."""
    start = fault_start(config.profile)
    end = start + np.timedelta64(FAULT_WINDOW_MINUTES, "m")
    runs = []
    for kind in FaultKind:
        scheduled = ScheduledFault(default_fault(kind), start, end)
        runs.append(FaultRun(kind, start, end, run(replace(config, faults=(scheduled,)))))
    return tuple(runs)


def score_fault(fault_run: FaultRun) -> FaultScore:
    """Detection delay and detection rate for one labelled fault run."""
    active = [sample for sample in fault_run.result.samples if sample.active_faults]
    first_detected = next((sample for sample in active if sample.state is not State.NORMAL), None)
    delay_s = None
    if first_detected is not None:
        delay_s = float((first_detected.timestamp - fault_run.start) / np.timedelta64(1, "s"))
    daylight = [sample for sample in active if sample.power_predicted >= POWER_FLOOR_W]
    rate = None
    if daylight:
        rate = sum(sample.state is not State.NORMAL for sample in daylight) / len(daylight)
    return FaultScore(fault_run.kind, delay_s, rate)


def confusion_matrix(fault_runs: Iterable[FaultRun]) -> ConfusionMatrix:
    """Daylight Samples of the fault runs, by fault-active truth and estimated State."""
    counts = [[0, 0, 0], [0, 0, 0]]
    for fault_run in fault_runs:
        for sample in fault_run.result.samples:
            if sample.power_predicted >= POWER_FLOOR_W:
                counts[int(bool(sample.active_faults))][STATE_ORDER.index(sample.state)] += 1
    return ConfusionMatrix((tuple(counts[0]), tuple(counts[1])))


def run_validation(config: RunConfig) -> ValidationReport:
    """The full validation for config: healthy metrics, the fault batch and false-alarm rates."""
    healthy_config = replace(config, faults=())
    healthy = run(healthy_config)
    fault_runs = fault_batch(config)
    scores = tuple(score_fault(fault_run) for fault_run in fault_runs)
    confusion = confusion_matrix(fault_runs)

    derived = derive_thresholds(config)
    derived_run = run(replace(healthy_config, thresholds=derived))

    delays = [score.delay_s for score in scores if score.delay_s is not None]
    fault_row = confusion.counts[1]
    fault_total = sum(fault_row)
    return ValidationReport(
        config=config,
        healthy=healthy,
        metrics=error_metrics(healthy),
        fault_runs=fault_runs,
        faults=scores,
        confusion=confusion,
        mean_delay_s=float(np.mean(delays)) if delays else None,
        detection_rate=(fault_row[1] + fault_row[2]) / fault_total if fault_total else None,
        false_alarm_rate=false_alarm_rate(healthy),
        derived_thresholds=derived,
        false_alarm_rate_derived=false_alarm_rate(derived_run),
    )


def _samples(source: RunResult | Iterable[Sample]) -> Sequence[Sample]:
    if isinstance(source, RunResult):
        return source.samples
    return list(source)
