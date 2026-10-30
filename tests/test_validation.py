from dataclasses import replace

import numpy as np
import pytest

from pvysics.faults import FaultKind, ScheduledFault, default_fault
from pvysics.profile import Profile
from pvysics.run import (
    POWER_FLOOR_W,
    RunConfig,
    Sample,
    State,
    Thresholds,
    bundled_run_config,
    run,
)
from pvysics.run_setup import derive_thresholds
from pvysics.validation import (
    FAULT_WINDOW_MINUTES,
    ConfusionMatrix,
    error_metrics,
    false_alarm_rate,
    fault_batch,
    fault_start,
    run_validation,
    score_fault,
)

COARSE_STEP_S = 600.0  # 10 minutes keeps the batch tests quick; the default is 1 minute
TOLERANCE_W = 1e-9  # the metrics must match plain numpy to this absolute tolerance, in watts


@pytest.fixture(scope="module")
def bundled_report():
    """The full-resolution bundled day with the default config, validated once for the module."""
    return run_validation(bundled_run_config(seed=0))


def coarse(**changes) -> RunConfig:
    return replace(bundled_run_config(seed=1), time_step_s=COARSE_STEP_S, **changes)


def sample(measured_w: float, predicted_w: float, state: State = State.NORMAL) -> Sample:
    return Sample(
        timestamp=np.datetime64("2025-01-15T10:00:00"),
        true_irradiance=800.0,
        true_temperature=25.0,
        measured_irradiance=800.0,
        measured_temperature=25.0,
        measured_voltage=30.0,
        measured_current=measured_w / 30.0,
        power_measured=measured_w,
        power_predicted=predicted_w,
        deviation_pct=0.0,
        state=state,
    )


def test_mae_rmse_and_mape_match_plain_numpy_on_the_same_healthy_samples():
    result = run(bundled_run_config(seed=0))

    metrics = error_metrics(result)

    measured = np.array([s.power_measured for s in result.samples])
    predicted = np.array([s.power_predicted for s in result.samples])
    daylight = predicted >= POWER_FLOOR_W
    lit = daylight & (measured >= POWER_FLOOR_W)
    error = measured[daylight] - predicted[daylight]
    relative = np.abs(measured[lit] - predicted[lit]) / measured[lit]
    assert metrics.mae_w == pytest.approx(np.mean(np.abs(error)), abs=TOLERANCE_W)
    assert metrics.rmse_w == pytest.approx(np.sqrt(np.mean(error**2)), abs=TOLERANCE_W)
    assert metrics.mape_pct == pytest.approx(np.mean(relative) * 100.0, abs=1e-9)
    assert metrics.sample_count == int(daylight.sum())
    assert metrics.mape_sample_count == int(lit.sum())


def test_metrics_accept_a_run_result_or_its_samples_alike():
    result = run(coarse())

    assert error_metrics(result) == error_metrics(result.samples)


def test_night_samples_are_left_out_of_every_metric():
    night = sample(measured_w=0.0, predicted_w=0.0)
    night_with_error = sample(measured_w=40.0, predicted_w=0.0)
    day = sample(measured_w=100.0, predicted_w=110.0)

    metrics = error_metrics([night, night_with_error, day])

    assert metrics.sample_count == 1
    assert metrics.mae_w == pytest.approx(10.0)
    assert metrics.rmse_w == pytest.approx(10.0)


def test_mape_skips_daylight_samples_whose_measured_power_is_near_zero():
    near_zero = sample(measured_w=0.5, predicted_w=50.0)  # daylight by prediction, dead by measurement
    day = sample(measured_w=100.0, predicted_w=110.0)

    metrics = error_metrics([near_zero, day])

    assert metrics.sample_count == 2  # MAE and RMSE still count it
    assert metrics.mae_w == pytest.approx((49.5 + 10.0) / 2)
    assert metrics.mape_sample_count == 1
    assert metrics.mape_pct == pytest.approx(10.0)  # 10 W off 100 W, and nothing from the near-zero sample


def test_metrics_refuse_a_run_with_no_daylight():
    with pytest.raises(ValueError, match="daylight"):
        error_metrics([sample(measured_w=0.0, predicted_w=0.0)])


def test_a_healthy_run_has_zero_false_alarms_at_the_default_thresholds():
    result = run(bundled_run_config(seed=0))

    assert false_alarm_rate(result) == 0.0
    assert {s.state for s in result.samples} == {State.NORMAL}


def test_false_alarm_rate_is_the_fraction_of_daylight_samples_not_normal():
    samples = [
        sample(100.0, 100.0, State.NORMAL),
        sample(100.0, 100.0, State.WARNING),
        sample(100.0, 100.0, State.ABNORMAL),
        sample(0.0, 0.0, State.ABNORMAL),  # night does not count
    ]

    assert false_alarm_rate(samples) == pytest.approx(2 / 3)


def test_fault_start_is_mid_morning_on_the_first_day():
    profile = bundled_run_config().profile

    assert fault_start(profile) == np.datetime64("2025-01-15T10:00:00")


def test_fault_start_needs_a_sample_at_or_after_mid_morning():
    profile = Profile(
        timestamps=np.array(["2025-01-15T06:00", "2025-01-15T07:00"], dtype="datetime64[s]"),
        irradiance=np.array([10.0, 20.0]),
        temperature=np.array([20.0, 21.0]),
    )

    with pytest.raises(ValueError, match="fault start"):
        fault_start(profile)


def test_fault_batch_has_one_labelled_run_per_fault_kind_at_the_same_time():
    batch = fault_batch(coarse())

    assert [fault_run.kind for fault_run in batch] == list(FaultKind)
    starts = {fault_run.start for fault_run in batch}
    ends = {fault_run.end for fault_run in batch}
    assert starts == {np.datetime64("2025-01-15T10:00:00")}
    assert ends == {np.datetime64("2025-01-15T10:00:00") + np.timedelta64(FAULT_WINDOW_MINUTES, "m")}


@pytest.mark.parametrize("kind", list(FaultKind))
def test_each_labelled_fault_is_active_only_inside_its_window(kind):
    fault_run = fault_batch(coarse())[list(FaultKind).index(kind)]

    for s in fault_run.result.samples:
        inside = fault_run.start <= s.timestamp < fault_run.end
        assert (kind in s.active_faults) == inside
        assert set(s.active_faults) <= {kind}


def test_the_batch_ignores_the_configs_own_scheduled_faults():
    stray = ScheduledFault(default_fault(FaultKind.SOILING), np.datetime64("2025-01-15T06:00:00"))
    batch = fault_batch(coarse(faults=(stray,)))

    for fault_run in batch:
        assert all(set(s.active_faults) <= {fault_run.kind} for s in fault_run.result.samples)


@pytest.mark.slow
def test_every_labelled_fault_is_detected_on_the_bundled_day_at_default_thresholds(bundled_report):
    for score in bundled_report.faults:
        assert score.delay_s is not None
        assert 0.0 <= score.delay_s < 60.0  # detected within the first Sample of the fault
        assert score.detection_rate == pytest.approx(1.0)
    assert bundled_report.mean_delay_s == pytest.approx(0.0)
    assert bundled_report.detection_rate == pytest.approx(1.0)


def test_confusion_matrix_counts_every_daylight_sample_of_the_fault_runs_once(bundled_report):
    matrix = bundled_report.confusion
    daylight_total = sum(
        sum(1 for s in fault_run.result.samples if s.power_predicted >= POWER_FLOOR_W)
        for fault_run in bundled_report.fault_runs
    )

    assert sum(sum(row) for row in matrix.counts) == daylight_total
    assert matrix.count(fault_active=True, state=State.ABNORMAL) == 5 * 60  # five faults, one hour each
    assert matrix.count(fault_active=True, state=State.NORMAL) == 0
    assert matrix.count(fault_active=False, state=State.ABNORMAL) == 0


def test_faults_that_are_never_detected_have_no_delay_and_zero_detection_rate():
    config = coarse(thresholds=Thresholds(warning_pct=150.0, abnormal_pct=199.0))

    report = run_validation(config)

    assert all(score.delay_s is None for score in report.faults)
    assert all(score.detection_rate == 0.0 for score in report.faults)
    assert report.mean_delay_s is None
    assert report.detection_rate == 0.0


def test_detection_delay_is_measured_from_the_fault_start_to_the_first_non_normal_sample():
    fault_run = fault_batch(coarse())[0]
    scored = score_fault(fault_run)

    first_flagged = next(
        s for s in fault_run.result.samples if s.active_faults and s.state is not State.NORMAL
    )
    assert scored.delay_s == (first_flagged.timestamp - fault_run.start) / np.timedelta64(1, "s")


def test_each_fault_reports_its_mean_deviation_and_the_healthy_run_its_baseline(bundled_report):
    by_kind = {score.kind.value: score for score in bundled_report.faults}

    assert all(score.mean_deviation_pct is not None for score in bundled_report.faults)
    assert by_kind["partial shading"].mean_deviation_pct < -5.0  # shading loses power, so the sign is negative
    healthy_daylight = [s for s in bundled_report.healthy.samples if s.power_predicted >= POWER_FLOOR_W]
    assert bundled_report.baseline_deviation_pct == pytest.approx(
        float(np.mean([s.deviation_pct for s in healthy_daylight]))
    )
    assert abs(bundled_report.baseline_deviation_pct) < 5.0  # the default mismatch is a small offset, not a fault


def test_report_false_alarm_rates_are_computed_at_config_and_at_derived_thresholds(bundled_report):
    config = bundled_report.config
    derived = derive_thresholds(config)

    assert bundled_report.derived_thresholds == derived
    assert bundled_report.false_alarm_rate == 0.0
    assert bundled_report.false_alarm_rate_derived == pytest.approx(
        false_alarm_rate(run(replace(config, faults=(), thresholds=derived)))
    )
    assert 0.0 <= bundled_report.false_alarm_rate_derived <= 1.0


def test_confusion_matrix_helper_reads_by_truth_and_state():
    matrix = ConfusionMatrix(((5, 1, 0), (2, 3, 4)))

    assert matrix.count(False, State.WARNING) == 1
    assert matrix.count(True, State.ABNORMAL) == 4
