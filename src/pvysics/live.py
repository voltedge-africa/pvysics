"""Live readings: a reading from a device, checked and scored by the twin as it arrives. Headless, no Qt.

A device (an ESP32 with a current and voltage sensor, a logger) sends one reading at a time: the irradiance,
the module temperature, and the voltage and current at the module's terminals, or the power. The twin scores
each reading with the rule a dataset row uses (dataset.score_row), so a live reading and the same row in a
file give the same Sample.

A live feed has no schedule. A Sample exists only for a reading that arrived, so starting to send in the
middle of the day, or pausing, raises nothing by itself; the app watches for silence separately.
"""

import csv
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from pvysics.dataset import (
    CURRENT_COLUMNS,
    IRRADIANCE_COLUMNS,
    POWER_COLUMNS,
    TEMPERATURE_COLUMNS,
    TIMESTAMP_COLUMNS,
    VOLTAGE_COLUMNS,
    default_datasets_dir,
    score_row,
)
from pvysics.run import Event, RunConfig, Sample

LIVE_DIR_ENV = "PVYSICS_LIVE_DIR"
LOG_COLUMNS = ("timestamp", "irradiance_w_m2", "temperature_c", "voltage_v", "current_a", "power_w")


class ReadingError(ValueError):
    """A reading that cannot be scored, with the reason in plain words."""


@dataclass(frozen=True)
class Reading:
    """One reading. A voltage of 0 means the device sent none: the twin then predicts the maximum power."""

    timestamp: np.datetime64
    irradiance: float  # W/m^2
    temperature: float  # degrees C
    voltage: float  # V
    current: float  # A
    power: float  # W


def now_stamp() -> np.datetime64:
    """The computer's own clock, in local time, to the second: the time of a reading that carries none."""
    return np.datetime64(datetime.now().replace(microsecond=0), "s")


def parse_reading(payload: object, received_at: np.datetime64 | None = None) -> Reading:
    """A reading from a decoded JSON object. Raises ReadingError, saying what is wrong.

    The keys are the dataset column names, in any case (`g`, `irradiance`, `irradiance_w_m2`; `t`, `temperature_c`;
    `v`, `voltage`; `i`, `current`; `power`). A reading needs irradiance, temperature, and either power or both
    voltage and current. `timestamp` is optional text such as 2025-01-15T10:00:00; without it the reading is
    stamped with `received_at`, or the computer's clock.
    """
    if not isinstance(payload, Mapping):
        raise ReadingError("a reading must be a JSON object, such as {\"g\": 640, \"t\": 32, \"v\": 29, \"i\": 5.2}")
    fields = {str(key).strip().lower(): value for key, value in payload.items()}
    irradiance = _number(fields, IRRADIANCE_COLUMNS, "irradiance")
    temperature = _number(fields, TEMPERATURE_COLUMNS, "temperature")
    voltage = _number(fields, VOLTAGE_COLUMNS, "voltage", required=False)
    current = _number(fields, CURRENT_COLUMNS, "current", required=False)
    power = _number(fields, POWER_COLUMNS, "power", required=False)
    if irradiance < 0.0:
        raise ReadingError("irradiance is negative")
    if power is None:
        if voltage is None or current is None:
            raise ReadingError("send the power, or both the voltage and the current")
        power = voltage * current
    return Reading(
        timestamp=_stamp(fields, received_at),
        irradiance=irradiance,
        temperature=temperature,
        voltage=0.0 if voltage is None else voltage,
        current=0.0 if current is None else current,
        power=power,
    )


class LiveScorer:
    """Scores readings in the order they arrive, and says when the State changes.

    It refuses a reading whose time does not come after the one before, so a device that resends or a clock
    that steps back cannot put the run's history out of order. It is not thread safe: one caller at a time.
    """

    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.accepted = 0
        self._last_stamp: np.datetime64 | None = None
        self._state = None

    @property
    def last_stamp(self) -> np.datetime64 | None:
        return self._last_stamp

    def score(self, reading: Reading) -> tuple[Sample, list[Event]]:
        """The reading's Sample and the Events it causes. Raises ReadingError if its time does not increase."""
        if self._last_stamp is not None and reading.timestamp <= self._last_stamp:
            raise ReadingError(
                f"time does not increase: {_label(reading.timestamp)} is not after {_label(self._last_stamp)}"
            )
        sample, _mpp = score_row(
            self.config,
            reading.timestamp,
            reading.irradiance,
            reading.temperature,
            reading.voltage,
            reading.current,
            reading.power,
        )
        events: list[Event] = []
        if self._state is not None and sample.state is not self._state:
            events.append(Event(sample.timestamp, "state", f"{self._state.value} -> {sample.state.value}"))
        self._state = sample.state
        self._last_stamp = reading.timestamp
        self.accepted += 1
        return sample, events


def _number(fields: Mapping[str, object], names: tuple[str, ...], role: str, required: bool = True) -> float | None:
    for name in names:
        key = name.lower()
        if key not in fields:
            continue
        value = fields[key]
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ReadingError(f"{role} is not a number")
        try:
            number = float(value)
        except ValueError:
            raise ReadingError(f"{role} is not a number: {value!r}") from None
        if not math.isfinite(number):
            raise ReadingError(f"{role} is not a finite number")
        return number
    if required:
        raise ReadingError(f"the reading has no {role}")
    return None


def _stamp(fields: Mapping[str, object], received_at: np.datetime64 | None) -> np.datetime64:
    for name in TIMESTAMP_COLUMNS:
        if name.lower() in fields:
            text = str(fields[name.lower()]).strip()
            try:
                return np.datetime64(text, "s")
            except ValueError:
                raise ReadingError(f"the time {text!r} is not a date and time such as 2025-01-15T10:00:00") from None
    return now_stamp() if received_at is None else received_at


def _label(stamp: np.datetime64) -> str:
    return np.datetime_as_string(stamp, unit="s").replace("T", " ")


def default_live_dir() -> Path:
    """Where live readings are kept: $PVYSICS_LIVE_DIR, else a `live` folder beside the datasets folder."""
    override = os.environ.get(LIVE_DIR_ENV)
    return Path(override) if override else default_datasets_dir().parent / "live"


class LiveLog:
    """Appends every accepted reading to a CSV file, so a feed is kept and can be imported as a dataset later.

    One file for each time the feed is started, named from that moment. The columns are the dataset template's,
    plus the power, so the file imports as it is. Each row is flushed as it is written, so a crash loses nothing.
    """

    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = directory / f"live-{stamp}.csv"
        self._handle = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._handle)
        self._writer.writerow(LOG_COLUMNS)
        self._handle.flush()

    def append(self, reading: Reading) -> None:
        self._writer.writerow(
            [
                np.datetime_as_string(reading.timestamp, unit="s"),
                reading.irradiance,
                reading.temperature,
                reading.voltage,
                reading.current,
                reading.power,
            ]
        )
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()
