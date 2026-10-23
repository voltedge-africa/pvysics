import subprocess
import sys
from dataclasses import replace

import numpy as np
import pytest

from pvysics.faults import DEFAULT_SEVERITY, Fault, FaultKind, ScheduledFault, default_fault
from pvysics.run import POWER_FLOOR_W, RunConfig, Simulation, State, bundled_run_config, run

COARSE_STEP_S = 600.0  # 10 minutes: keeps the suite fast; the default is 1 minute
ORIGIN = np.datetime64("2025-01-15T00:00:00")
FAULT_START = np.datetime64("2025-01-15T11:00")
FAULT_END = np.datetime64("2025-01-15T14:00")
DETECTION_DELAY_SAMPLES = 1  # an injected fault must be Abnormal within this many samples
POWER_FAULTS = [
    FaultKind.PARTIAL_SHADING,
    FaultKind.SOILING,
    FaultKind.SERIES_RESISTANCE_RISE,
    FaultKind.DIODE_FAILURE,
]
HEALTHY = replace(bundled_run_config(seed=1), time_step_s=COARSE_STEP_S)


def scheduled(kind: FaultKind, end: np.datetime64 | None = FAULT_END) -> RunConfig:
    entry = ScheduledFault(default_fault(kind), FAULT_START, end)
    return replace(HEALTHY, faults=(entry,))


def paired_window(healthy, faulted):
    """Healthy and faulted samples at the same times, daylight inside the fault window."""
    healthy_by_time = {sample.timestamp: sample for sample in healthy.samples}
    return [
        (healthy_by_time[sample.timestamp], sample)
        for sample in faulted.samples
        if FAULT_START <= sample.timestamp < FAULT_END and sample.power_predicted >= POWER_FLOOR_W
    ]


def offset_s(stamp: np.datetime64) -> float:
    return float((stamp - ORIGIN) / np.timedelta64(1, "s"))


@pytest.mark.parametrize("kind", POWER_FAULTS)
def test_fault_lowers_the_plant_power_while_the_twin_prediction_stays_healthy(kind):
    healthy = run(HEALTHY)
    faulted = run(scheduled(kind))

    pairs = paired_window(healthy, faulted)

    assert pairs
    assert all(after.power_measured < before.power_measured for before, after in pairs)
    assert all(after.power_predicted == before.power_predicted for before, after in pairs)
    assert all(after.measured_temperature == before.measured_temperature for before, after in pairs)


def test_sensor_drift_makes_the_twin_wrong_while_the_plant_power_is_unchanged():
    healthy = run(HEALTHY)
    faulted = run(scheduled(FaultKind.SENSOR_DRIFT))

    pairs = paired_window(healthy, faulted)

    assert pairs
    assert all(after.power_measured == before.power_measured for before, after in pairs)
    assert all(after.power_predicted > before.power_predicted for before, after in pairs)
    noon = next(after for _, after in pairs if after.timestamp == np.datetime64("2025-01-15T12:00"))
    assert noon.deviation_pct < -10.0
    assert noon.state is State.ABNORMAL


def test_scheduled_fault_is_active_from_its_start_until_its_end():
    result = run(scheduled(FaultKind.PARTIAL_SHADING))

    faulted_stamps = [sample.timestamp for sample in result.samples if sample.active_faults]

    assert faulted_stamps[0] == FAULT_START
    assert faulted_stamps[-1] == np.datetime64("2025-01-15T13:50")
    after = [sample for sample in result.samples if sample.timestamp >= FAULT_END]
    assert all(sample.active_faults == () for sample in after)


def test_fault_changes_are_logged_as_fault_events_at_the_step_they_apply():
    result = run(scheduled(FaultKind.PARTIAL_SHADING))

    fault_events = [
        (event.timestamp, event.detail) for event in result.events if event.kind == "fault"
    ]

    assert fault_events == [
        (FAULT_START, "none -> partial shading"),
        (FAULT_END, "partial shading -> none"),
    ]


def test_live_injection_gives_the_same_samples_and_events_as_the_same_fault_scheduled():
    scheduled_result = run(scheduled(FaultKind.DIODE_FAILURE, end=None))
    simulation = Simulation(HEALTHY)
    samples = []
    while offset_s(FAULT_START) > simulation.next_offset_s:
        samples.append(simulation.step())
    simulation.inject(default_fault(FaultKind.DIODE_FAILURE))
    while not simulation.finished:
        samples.append(simulation.step())

    assert samples == scheduled_result.samples
    assert simulation.drain_events() == scheduled_result.events


def test_faults_do_not_change_the_noise_draws():
    healthy = run(HEALTHY)
    faulted = run(scheduled(FaultKind.SENSOR_DRIFT))

    assert [s.measured_temperature for s in faulted.samples] == [
        s.measured_temperature for s in healthy.samples
    ]


@pytest.mark.parametrize("kind", list(FaultKind))
def test_injected_fault_at_midday_drives_the_state_to_abnormal_within_one_sample(kind):
    simulation = Simulation(bundled_run_config(seed=1))  # the default one-minute step
    while offset_s(np.datetime64("2025-01-15T12:00")) > simulation.next_offset_s:
        simulation.step()

    simulation.inject(default_fault(kind))
    states = [simulation.step().state for _ in range(DETECTION_DELAY_SAMPLES)]

    assert State.ABNORMAL in states


def test_clear_all_returns_the_plant_to_normal_and_cancels_the_schedule():
    simulation = Simulation(
        replace(
            HEALTHY,
            faults=(ScheduledFault(default_fault(FaultKind.SOILING), FAULT_START, None),),
        )
    )
    simulation.inject(default_fault(FaultKind.PARTIAL_SHADING))
    while offset_s(np.datetime64("2025-01-15T11:30")) > simulation.next_offset_s:
        simulation.step()
    assert simulation.step().state is State.ABNORMAL

    simulation.clear_faults()
    after = [simulation.step() for _ in range(3)]

    assert all(sample.active_faults == () for sample in after)
    assert all(sample.state is State.NORMAL for sample in after)


@pytest.mark.parametrize("kind", list(FaultKind))
def test_default_severity_is_a_valid_fault(kind):
    assert Fault(kind, DEFAULT_SEVERITY[kind]).severity == DEFAULT_SEVERITY[kind]


@pytest.mark.parametrize(
    ("kind", "severity"),
    [
        (FaultKind.PARTIAL_SHADING, 1.5),
        (FaultKind.SOILING, -0.1),
        (FaultKind.DIODE_FAILURE, 1.0),
        (FaultKind.SERIES_RESISTANCE_RISE, -1.0),
        (FaultKind.SENSOR_DRIFT, -1.0),
        (FaultKind.SOILING, float("nan")),
    ],
)
def test_out_of_range_severity_is_rejected(kind, severity):
    with pytest.raises(ValueError):
        Fault(kind, severity)


def test_faults_import_without_qt():
    code = (
        "import sys, pvysics.faults, pvysics.alarms; "
        "assert not any(m.startswith('PyQt') for m in sys.modules)"
    )

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
