"""The plotted values of a run so far, one column per name, for the windows that chart it."""

import numpy as np

from pvysics.run import Sample

COLUMNS = (
    "hours",
    "power_measured",
    "power_predicted",
    "deviation",
    "irradiance",
    "temperature",
    "voltage",
    "current",
    "energy_wh",
)
COLUMN_INDEX = {name: index for index, name in enumerate(COLUMNS)}
INITIAL_CAPACITY = 1024


class SampleColumns:
    """The plotted values of the run so far, one column per name in COLUMNS.

    Rows are appended in place into arrays that grow by doubling, so an append costs only
    the new Samples and a read is a view.
    """

    def __init__(self) -> None:
        self._data = np.empty((len(COLUMNS), INITIAL_CAPACITY))
        self._count = 0

    def clear(self) -> None:
        self._count = 0

    def append(self, samples: list[Sample], origin: np.datetime64, energies: list[float]) -> None:
        rows = np.array([_row(sample, origin, energy) for sample, energy in zip(samples, energies)], dtype=float).T
        needed = self._count + rows.shape[1]
        if needed > self._data.shape[1]:
            grown = np.empty((len(COLUMNS), max(needed, 2 * self._data.shape[1])))
            grown[:, : self._count] = self._data[:, : self._count]
            self._data = grown
        self._data[:, self._count : needed] = rows
        self._count = needed

    def column(self, name: str) -> np.ndarray:
        return self._data[COLUMN_INDEX[name], : self._count]


def _row(sample: Sample, origin: np.datetime64, energy_wh: float) -> list[float]:
    hours = (sample.timestamp - origin) / np.timedelta64(1, "h")
    return [
        hours,
        sample.power_measured,
        sample.power_predicted,
        sample.deviation_pct,
        sample.measured_irradiance,
        sample.measured_temperature,
        sample.measured_voltage,
        sample.measured_current,
        energy_wh,
    ]
