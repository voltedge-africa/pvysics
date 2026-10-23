"""Headless statistics for the live Dashboard charts: the power deviation histogram and the time in each State.

No Qt. Both classes take only the Samples that arrived since the last call, so a UI tick costs the
new Samples and not the whole run.

The histogram counts daylight Samples only (predicted power at least POWER_FLOOR_W). Below that floor
the engine reports a deviation of 0, which says nothing about the plant, so it would pile up in the
0 % bin. Time in state counts every Sample, night included, as the engine reports its State.
"""

from collections.abc import Iterable

import numpy as np

from pvysics.run import POWER_FLOOR_W, Sample, State

HISTOGRAM_LIMIT_PCT = 10.0  # the range is symmetric about zero: -10 % to +10 %
HISTOGRAM_BIN_PCT = 0.5  # 40 bins; the default abnormal limit is the edge of the range


class DeviationHistogram:
    """Counts of the daylight power deviation in fixed bins, with the counts outside the range kept apart."""

    def __init__(self, limit_pct: float = HISTOGRAM_LIMIT_PCT, bin_pct: float = HISTOGRAM_BIN_PCT) -> None:
        bins = round(2.0 * limit_pct / bin_pct)
        self._edges = np.linspace(-limit_pct, limit_pct, bins + 1)
        self._counts = np.zeros(bins, dtype=int)
        self._below = 0
        self._above = 0

    @property
    def edges(self) -> np.ndarray:
        """The bin edges in percent, from the lowest to the highest."""
        return self._edges

    @property
    def centres(self) -> np.ndarray:
        return (self._edges[:-1] + self._edges[1:]) / 2.0

    @property
    def bin_width_pct(self) -> float:
        return float(self._edges[1] - self._edges[0])

    @property
    def counts(self) -> np.ndarray:
        return self._counts

    @property
    def total(self) -> int:
        """Daylight Samples inside the range."""
        return int(self._counts.sum())

    @property
    def below_range(self) -> int:
        return self._below

    @property
    def above_range(self) -> int:
        return self._above

    def add(self, samples: Iterable[Sample]) -> None:
        """Count the daylight Samples in samples, as well as the ones before them."""
        deviations = np.array(
            [sample.deviation_pct for sample in samples if sample.power_predicted >= POWER_FLOOR_W],
            dtype=float,
        )
        if deviations.size == 0:
            return
        counts, _edges = np.histogram(deviations, bins=self._edges)
        self._counts += counts
        self._below += int(np.count_nonzero(deviations < self._edges[0]))
        self._above += int(np.count_nonzero(deviations > self._edges[-1]))

    def clear(self) -> None:
        self._counts[:] = 0
        self._below = 0
        self._above = 0


class StateTimes:
    """Simulated seconds spent in each State, from the time between consecutive Samples.

    The time from one Sample to the next belongs to the State of the earlier one, so the times add up
    to the elapsed time from the first Sample to the latest. The latest Sample's time is not yet known.
    """

    def __init__(self) -> None:
        self._seconds = {state: 0.0 for state in State}
        self._last: Sample | None = None

    def seconds_in(self, state: State) -> float:
        return self._seconds[state]

    def fraction_in(self, state: State) -> float:
        """The share of the elapsed time spent in state, from 0 to 1; 0 before any time has passed."""
        total = self.total_seconds
        return self._seconds[state] / total if total > 0.0 else 0.0

    @property
    def total_seconds(self) -> float:
        return sum(self._seconds.values())

    def add(self, samples: Iterable[Sample]) -> None:
        """Credit the time up to each of samples, in time order, to the State of the Sample before it."""
        for sample in samples:
            if self._last is not None:
                gap = (sample.timestamp - self._last.timestamp) / np.timedelta64(1, "s")
                self._seconds[self._last.state] += float(gap)
            self._last = sample

    def clear(self) -> None:
        self._seconds = {state: 0.0 for state in State}
        self._last = None
