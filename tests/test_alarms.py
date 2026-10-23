from dataclasses import replace

import numpy as np

from pvysics.alarms import AlarmLog
from pvysics.faults import Fault, FaultKind, ScheduledFault
from pvysics.run import State, Thresholds, bundled_run_config, run

COARSE_STEP_S = 600.0
FAULT_START = np.datetime64("2025-01-15T12:00")
FAULT_END = np.datetime64("2025-01-15T13:00")


def fed(result) -> AlarmLog:
    log = AlarmLog()
    for sample in result.samples:
        log.record(sample)
    return log


def test_a_fault_raises_one_abnormal_alarm_and_the_return_to_normal_is_not_an_alarm():
    config = replace(
        bundled_run_config(seed=1),
        time_step_s=COARSE_STEP_S,
        faults=(ScheduledFault(Fault(FaultKind.PARTIAL_SHADING, 0.3), FAULT_START, FAULT_END),),
    )
    result = run(config)

    log = fed(result)

    assert [(event.kind, event.detail) for event in result.events if event.kind == "state"] == [
        ("state", "Normal -> Abnormal"),
        ("state", "Abnormal -> Normal"),
    ]
    assert len(log.alarms) == 1
    alarm = log.alarms[0]
    assert alarm.timestamp == FAULT_START
    assert alarm.severity is State.ABNORMAL
    assert alarm.cause == "partial shading"
    assert alarm.deviation_pct < -10.0
    assert not alarm.acknowledged


def test_alarm_cause_is_unknown_when_no_fault_is_active():
    tight = replace(
        bundled_run_config(seed=7),
        time_step_s=COARSE_STEP_S,
        thresholds=Thresholds(warning_pct=0.5, abnormal_pct=1.0),
    )

    log = fed(run(tight))

    assert log.alarms
    assert all(alarm.cause == "unknown" for alarm in log.alarms)


def test_every_state_change_to_warning_or_abnormal_raises_an_alarm_in_order():
    tight = replace(
        bundled_run_config(seed=7),
        time_step_s=COARSE_STEP_S,
        thresholds=Thresholds(warning_pct=0.5, abnormal_pct=1.0),
    )
    result = run(tight)
    changes = [
        later
        for earlier, later in zip(result.samples, result.samples[1:])
        if later.state is not earlier.state and later.state is not State.NORMAL
    ]

    log = fed(result)

    assert changes
    assert [alarm.timestamp for alarm in log.alarms] == [sample.timestamp for sample in changes]
    assert [alarm.severity for alarm in log.alarms] == [sample.state for sample in changes]


def test_an_alarm_can_be_acknowledged_and_the_unacknowledged_count_drops():
    config = replace(
        bundled_run_config(seed=1),
        time_step_s=COARSE_STEP_S,
        faults=(ScheduledFault(Fault(FaultKind.SOILING, 0.2), FAULT_START, FAULT_END),),
    )
    log = fed(run(config))
    assert log.unacknowledged_count == 1

    log.acknowledge(0)

    assert log.alarms[0].acknowledged
    assert log.unacknowledged_count == 0
