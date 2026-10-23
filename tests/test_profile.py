from datetime import date

import numpy as np
import pytest

from pvysics.profile import ProfileError, load_bundled_profile, parse_profile_csv

HEADER = "YEAR,MO,DY,HR,ALLSKY_SFC_SW_DWN,T2M"


def day_csv(irradiance=None, temperature="20.0", drop_hours=(), reverse=False):
    """CSV text for 2025-01-15, one row per hour, with optional overrides."""
    irradiance = irradiance or {}
    rows = [
        f"2025,1,15,{hour},{irradiance.get(hour, '0.0')},{temperature}"
        for hour in range(24)
        if hour not in drop_hours
    ]
    if reverse:
        rows.reverse()
    return "\n".join([HEADER, *rows]) + "\n"


def test_bundled_day_is_24_hourly_steps_starting_at_midnight():
    profile = load_bundled_profile(date(2025, 1, 15))

    assert len(profile.timestamps) == 24
    assert profile.timestamps[0] == np.datetime64("2025-01-15T00:00:00")
    assert np.all(np.diff(profile.timestamps) == np.timedelta64(1, "h"))


@pytest.mark.parametrize("day", [date(2025, 1, 15), date(2025, 1, 16), date(2025, 1, 17)])
def test_irradiance_is_never_negative_on_bundled_days(day):
    profile = load_bundled_profile(day)

    assert np.all(profile.irradiance >= 0.0)


def test_bundled_day_is_dark_at_midnight_and_bright_at_midday():
    profile = load_bundled_profile(date(2025, 1, 15))

    assert profile.irradiance[0] == 0.0
    assert profile.irradiance[10] > 300.0


def test_parsed_values_are_kept_for_the_chosen_day():
    profile = parse_profile_csv(day_csv({12: "800.5"}, temperature="31.25"), date(2025, 1, 15))

    assert profile.irradiance[12] == pytest.approx(800.5)
    assert profile.temperature[12] == pytest.approx(31.25)


def test_day_missing_from_the_data_is_rejected():
    with pytest.raises(ProfileError):
        load_bundled_profile(date(2025, 2, 1))


def test_gap_in_hourly_rows_is_rejected():
    with pytest.raises(ProfileError):
        parse_profile_csv(day_csv(drop_hours=(7,)), date(2025, 1, 15))


def test_missing_value_marker_is_rejected():
    with pytest.raises(ProfileError):
        parse_profile_csv(day_csv({9: "-999"}), date(2025, 1, 15))


def test_negative_irradiance_is_rejected():
    with pytest.raises(ProfileError):
        parse_profile_csv(day_csv({9: "-5.0"}), date(2025, 1, 15))


def test_rows_out_of_time_order_are_rejected():
    with pytest.raises(ProfileError):
        parse_profile_csv(day_csv(reverse=True), date(2025, 1, 15))
