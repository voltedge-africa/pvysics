"""Profile statistics for the fetched-profile preview, on small profiles with known numbers. Headless."""

from datetime import date

import numpy as np
import pytest

from pvysics.profile import Profile
from pvysics.profile_stats import MAX_PLOT_POINTS, plot_indices, profile_stats


def profile_from(start: str, step_minutes: int, irradiance, temperature) -> Profile:
    count = len(irradiance)
    stamps = np.datetime64(start, "s") + np.arange(count) * np.timedelta64(step_minutes, "m")
    return Profile(
        timestamps=stamps.astype("datetime64[s]"),
        irradiance=np.array(irradiance, dtype=float),
        temperature=np.array(temperature, dtype=float),
        name="known",
    )


def two_hourly_days() -> Profile:
    """15 and 16 January 2025, hourly. G is 100 on the first day and 200 on the second, from 06:00 to 17:00 only.
    T is 10 C on the first day and 30 C on the second. Each day has 12 hours of sun.
    """
    hours = np.arange(24)
    sun = ((hours >= 6) & (hours < 18)).astype(float)
    irradiance = np.concatenate([100.0 * sun, 200.0 * sun])
    temperature = np.concatenate([np.full(24, 10.0), np.full(24, 30.0)])
    return profile_from("2025-01-15T00:00", 60, irradiance, temperature)


def test_statistics_of_a_known_two_day_profile_match_the_hand_calculation():
    stats = profile_stats(two_hourly_days())

    assert stats.samples == 48
    assert stats.first == np.datetime64("2025-01-15T00:00:00")
    assert stats.last == np.datetime64("2025-01-16T23:00:00")
    assert stats.days == 2
    assert stats.step_s == pytest.approx(3600.0)
    assert stats.peak_g == pytest.approx(200.0)
    assert stats.peak_g_at == np.datetime64("2025-01-16T06:00:00")
    assert stats.daylight_samples == 24  # the samples with G above zero
    assert stats.mean_t == pytest.approx(20.0)
    assert stats.min_t == pytest.approx(10.0)
    assert stats.max_t == pytest.approx(30.0)


def test_each_day_has_its_own_peak_in_date_order():
    stats = profile_stats(two_hourly_days())

    assert stats.daily_peak_g == ((date(2025, 1, 15), 100.0), (date(2025, 1, 16), 200.0))


def test_mean_daily_energy_sums_each_hourly_step_as_g_times_its_length():
    # Day one: 12 h at 100 W/m2 = 1200 Wh/m2. Day two: 12 h at 200 W/m2 = 2400 Wh/m2. Mean of the two days: 1800.
    stats = profile_stats(two_hourly_days())

    assert stats.mean_daily_energy_wh_m2 == pytest.approx(1800.0)


def test_energy_uses_the_step_length_for_a_quarter_hour_profile():
    # 96 steps of 15 minutes at 400 W/m2 is 24 h at 400 W/m2: 9600 Wh/m2 for the one day.
    profile = profile_from("2025-03-01T00:00", 15, np.full(96, 400.0), np.full(96, 25.0))

    stats = profile_stats(profile)

    assert stats.step_s == pytest.approx(900.0)
    assert stats.days == 1
    assert stats.mean_daily_energy_wh_m2 == pytest.approx(9600.0)


def test_a_tie_for_the_peak_is_reported_at_its_first_occurrence():
    profile = profile_from("2025-01-15T00:00", 60, [0.0, 500.0, 0.0, 500.0], [20.0] * 4)

    stats = profile_stats(profile)

    assert stats.peak_g_at == np.datetime64("2025-01-15T01:00:00")


def test_a_range_that_crosses_midnight_counts_both_calendar_days():
    profile = profile_from("2025-01-15T22:00", 60, [1.0, 2.0, 3.0, 4.0], [20.0] * 4)  # 22:00 to 01:00

    stats = profile_stats(profile)

    assert stats.days == 2
    assert stats.daily_peak_g == ((date(2025, 1, 15), 2.0), (date(2025, 1, 16), 4.0))


def test_plot_indices_keep_every_point_of_a_short_profile():
    assert list(plot_indices(744)) == list(range(744))


def test_plot_indices_are_bounded_and_keep_the_first_and_last_sample_of_a_long_profile():
    indices = plot_indices(100000)

    assert len(indices) == MAX_PLOT_POINTS
    assert indices[0] == 0
    assert indices[-1] == 99999
    assert np.all(np.diff(indices) > 0)


def test_statistics_use_every_sample_even_when_the_drawing_skips_some():
    irradiance = np.zeros(5000)
    irradiance[4321] = 950.0  # a sample the drawing of a 5000-sample profile does not pick
    profile = profile_from("2025-01-15T00:00", 60, irradiance, np.full(5000, 20.0))

    stats = profile_stats(profile)

    assert stats.peak_g == pytest.approx(950.0)
    assert stats.daylight_samples == 1
