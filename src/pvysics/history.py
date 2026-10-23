"""History: the Samples and Events of the current run, kept so a Dashboard opened mid-run can show them.

Headless, no Qt. The app feeds it from the data bus and clears it on reset. Energy is the
trapezoid integral of P measured over time, in watt-hours.
"""

import numpy as np

from pvysics.run import Event, Sample


class RunHistory:
    """Every Sample and Event of the run so far, in time order, plus the energy generated."""

    def __init__(self) -> None:
        self._samples: list[Sample] = []
        self._events: list[Event] = []
        self._energy_wh = 0.0

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def latest(self) -> Sample | None:
        return self._samples[-1] if self._samples else None

    @property
    def origin(self) -> np.datetime64 | None:
        """The timestamp of the first Sample of the run, or None before any Sample."""
        return self._samples[0].timestamp if self._samples else None

    @property
    def energy_wh(self) -> float:
        return self._energy_wh

    def samples_from(self, index: int) -> list[Sample]:
        """The Samples from position index onwards, in time order."""
        return self._samples[index:]

    def events_from(self, index: int) -> list[Event]:
        return self._events[index:]

    def record_sample(self, sample: Sample) -> None:
        if self._samples:
            previous = self._samples[-1]
            hours = (sample.timestamp - previous.timestamp) / np.timedelta64(1, "h")
            self._energy_wh += (previous.power_measured + sample.power_measured) / 2.0 * hours
        self._samples.append(sample)

    def record_event(self, event: Event) -> None:
        self._events.append(event)

    def clear(self) -> None:
        self._samples.clear()
        self._events.clear()
        self._energy_wh = 0.0
