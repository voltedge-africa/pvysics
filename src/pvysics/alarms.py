"""Alarms: one per State change to Warning or Abnormal, with a probable cause. Headless, no Qt.

A change back to Normal is not an alarm; it is an Event on the run. Each alarm names the
Faults active on the Sample that raised it, or says "unknown" when none is active.
"""

from dataclasses import dataclass, replace

import numpy as np

from pvysics.run import Sample, State

UNKNOWN_CAUSE = "unknown"


@dataclass(frozen=True)
class Alarm:
    timestamp: np.datetime64
    severity: State  # Warning or Abnormal
    cause: str  # the active Faults, or "unknown"
    deviation_pct: float
    acknowledged: bool = False


class AlarmLog:
    """The alarms raised so far in a run, fed one Sample at a time in time order."""

    def __init__(self) -> None:
        self._alarms: list[Alarm] = []
        self._state: State | None = None

    @property
    def alarms(self) -> tuple[Alarm, ...]:
        return tuple(self._alarms)

    @property
    def unacknowledged_count(self) -> int:
        return sum(not alarm.acknowledged for alarm in self._alarms)

    def record(self, sample: Sample) -> Alarm | None:
        """Add an alarm if the State changed to Warning or Abnormal. Returns the new alarm."""
        previous, self._state = self._state, sample.state
        if sample.state is State.NORMAL or sample.state is previous:
            return None
        names = ", ".join(kind.value for kind in sample.active_faults)
        alarm = Alarm(
            timestamp=sample.timestamp,
            severity=sample.state,
            cause=names or UNKNOWN_CAUSE,
            deviation_pct=sample.deviation_pct,
        )
        self._alarms.append(alarm)
        return alarm

    def acknowledge(self, index: int) -> None:
        self._alarms[index] = replace(self._alarms[index], acknowledged=True)

    def clear(self) -> None:
        self._alarms.clear()
        self._state = None
