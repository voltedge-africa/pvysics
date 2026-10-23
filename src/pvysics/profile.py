"""Profile loader: the hourly irradiance and temperature that drive a run."""

import csv
import io
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from importlib.resources import files

import numpy as np
from numpy.typing import NDArray

BUNDLED_CSV = "durban_power_hourly.csv"
MISSING_VALUE = -999.0


class ProfileError(ValueError):
    """The profile data is missing, has gaps, or has invalid values."""


@dataclass(frozen=True)
class Profile:
    """One day of hourly data: G in W/m^2 (mean over the hour) and T in degrees C."""

    timestamps: NDArray[np.datetime64]
    irradiance: NDArray[np.float64]
    temperature: NDArray[np.float64]


def parse_profile_csv(text: str, day: date) -> Profile:
    """Build the Profile for `day` from NASA POWER style CSV text.

    Rules: the day needs 24 hourly rows, 00:00 to 23:00, in order with no gaps.
    Missing-value markers and non-finite values are rejected, not filled.
    Irradiance must not be negative.
    """
    stamps: list[datetime] = []
    irradiance: list[float] = []
    temperature: list[float] = []
    for row in csv.DictReader(io.StringIO(text)):
        row_day = date(int(row["YEAR"]), int(row["MO"]), int(row["DY"]))
        if row_day != day:
            continue
        stamps.append(datetime(day.year, day.month, day.day, int(row["HR"])))
        irradiance.append(_value(row["ALLSKY_SFC_SW_DWN"], "irradiance"))
        temperature.append(_value(row["T2M"], "temperature"))

    start = datetime(day.year, day.month, day.day)
    expected = [start + timedelta(hours=hour) for hour in range(24)]
    if stamps != expected:
        raise ProfileError(
            f"{day}: expected 24 consecutive hourly rows from 00:00 to 23:00, found {len(stamps)}"
        )
    if any(value < 0.0 for value in irradiance):
        raise ProfileError(f"{day}: irradiance is negative")

    return Profile(
        timestamps=np.array(stamps, dtype="datetime64[s]"),
        irradiance=np.array(irradiance, dtype=np.float64),
        temperature=np.array(temperature, dtype=np.float64),
    )


def load_bundled_profile(day: date) -> Profile:
    """Load one day from the sample bundled with the package."""
    text = (files("pvysics") / "data" / BUNDLED_CSV).read_text(encoding="utf-8")
    return parse_profile_csv(text, day)


def _value(text: str, name: str) -> float:
    value = float(text)
    if value == MISSING_VALUE or not math.isfinite(value):
        raise ProfileError(f"missing {name} value")
    return value
