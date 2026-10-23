"""Statistics of a Profile for its preview, and the points to draw it with. Headless: no Qt.

The statistics describe every sample of the profile. The preview draws at most MAX_PLOT_POINTS of them
(plot_indices), so a long range draws quickly, and the numbers never come from the drawn points.

Each G is the mean over its step, so the energy of one step is G times the step length in hours, and
the energy of the profile is the sum over its steps. The mean daily energy divides that total by the
duration the samples cover, in days.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray

from pvysics.profile import Profile

MAX_PLOT_POINTS = 1000  # the most points one chart draws; a profile with fewer is drawn in full
SECONDS_PER_HOUR = 3600.0
HOURS_PER_DAY = 24.0


@dataclass(frozen=True)
class ProfileStats:
    samples: int
    first: np.datetime64
    last: np.datetime64
    days: int  # calendar days the samples fall on
    step_s: float  # seconds between samples
    peak_g: float  # W/m^2
    peak_g_at: np.datetime64  # the first sample that has the peak
    daily_peak_g: tuple[tuple[date, float], ...]  # (day, peak G that day), in date order
    daylight_samples: int  # samples with G above zero
    mean_t: float  # degrees C
    min_t: float
    max_t: float
    mean_daily_energy_wh_m2: float  # total energy divided by the duration covered, in days


def profile_stats(profile: Profile) -> ProfileStats:
    """The statistics of every sample in profile. Profile times are sorted and evenly spaced (profile.py checks this)."""
    stamps = profile.timestamps
    irradiance = profile.irradiance
    temperature = profile.temperature
    step_s = float((stamps[1] - stamps[0]) / np.timedelta64(1, "s"))
    step_h = step_s / SECONDS_PER_HOUR

    days = stamps.astype("datetime64[D]")
    day_starts = np.flatnonzero(np.r_[True, days[1:] != days[:-1]])  # times are sorted, so each day is one run
    daily_peaks = np.maximum.reduceat(irradiance, day_starts)

    duration_days = len(stamps) * step_h / HOURS_PER_DAY
    return ProfileStats(
        samples=len(stamps),
        first=stamps[0],
        last=stamps[-1],
        days=len(day_starts),
        step_s=step_s,
        peak_g=float(irradiance.max()),
        peak_g_at=stamps[int(np.argmax(irradiance))],
        daily_peak_g=tuple(
            (day.item(), float(peak)) for day, peak in zip(days[day_starts], daily_peaks)
        ),
        daylight_samples=int(np.count_nonzero(irradiance > 0.0)),
        mean_t=float(temperature.mean()),
        min_t=float(temperature.min()),
        max_t=float(temperature.max()),
        mean_daily_energy_wh_m2=float(irradiance.sum()) * step_h / duration_days,
    )


def plot_indices(count: int, limit: int = MAX_PLOT_POINTS) -> NDArray[np.intp]:
    """The sample positions to draw: all of them up to `limit`, else evenly spaced ones that keep the first and last."""
    if count <= limit:
        return np.arange(count)
    return np.linspace(0, count - 1, limit).round().astype(np.intp)
