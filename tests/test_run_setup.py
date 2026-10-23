"""Setup checks, derived thresholds and the run summary. Headless: no GUI."""

from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from pvysics.faults import FaultKind, ScheduledFault, default_fault
from pvysics.profile import Profile, load_bundled_profile
from pvysics.run import (
    POWER_FLOOR_W,
    Mismatch,
    SensorModel,
    Site,
    Thresholds,
    bundled_run_config,
    run,
)
from pvysics.run_setup import derive_thresholds, summary_rows, validate_config


def test_default_setup_has_no_problems():
    assert validate_config(bundled_run_config()) == []


@pytest.mark.parametrize(
    ("thresholds", "word"),
    [
        (Thresholds(warning_pct=5.0, abnormal_pct=5.0), "abnormal"),
        (Thresholds(warning_pct=10.0, abnormal_pct=5.0), "abnormal"),
        (Thresholds(warning_pct=0.0, abnormal_pct=5.0), "warning"),
        (Thresholds(warning_pct=-1.0, abnormal_pct=5.0), "warning"),
    ],
)
def test_thresholds_must_satisfy_abnormal_above_warning_above_zero(thresholds, word):
    problems = validate_config(replace(bundled_run_config(), thresholds=thresholds))

    assert any(word in problem.lower() for problem in problems)


def test_mismatch_that_removes_series_resistance_is_a_problem():
    config = replace(bundled_run_config(), mismatch=Mismatch(series_resistance_pct=-100.0))

    assert any("Rs" in problem for problem in validate_config(config))


def test_negative_noise_and_negative_seed_are_problems():
    config = replace(
        bundled_run_config(),
        sensors=SensorModel(irradiance_noise_pct=-0.5),
        seed=-1,
    )

    problems = validate_config(config)

    assert any("noise" in problem.lower() for problem in problems)
    assert any("seed" in problem.lower() for problem in problems)


@pytest.mark.parametrize(
    "site",
    [Site(latitude_deg=95.0), Site(longitude_deg=-181.0), Site(tilt_deg=120.0), Site(azimuth_deg=-5.0)],
)
def test_site_values_outside_their_range_are_problems(site):
    assert validate_config(replace(bundled_run_config(), site=site))


def test_derived_limits_are_mean_plus_two_and_three_sigma_of_healthy_deviation():
    config = bundled_run_config(seed=0)
    healthy = replace(config, faults=(), thresholds=Thresholds())
    deviations = np.array(
        [abs(s.deviation_pct) for s in run(healthy).samples if s.power_predicted >= POWER_FLOOR_W]
    )

    thresholds = derive_thresholds(config)

    assert thresholds.warning_pct == pytest.approx(deviations.mean() + 2 * deviations.std())
    assert thresholds.abnormal_pct == pytest.approx(deviations.mean() + 3 * deviations.std())
    assert validate_config(replace(config, thresholds=thresholds)) == []


def test_derived_limits_ignore_the_current_thresholds():
    config = bundled_run_config(seed=0)
    loose = replace(config, thresholds=Thresholds(warning_pct=30.0, abnormal_pct=40.0))

    assert derive_thresholds(loose) == derive_thresholds(config)


def test_derived_limits_do_not_depend_on_scheduled_faults():
    config = bundled_run_config(seed=0)
    start = config.profile.timestamps[0]
    fault = ScheduledFault(default_fault(FaultKind.PARTIAL_SHADING), start=start)

    assert derive_thresholds(replace(config, faults=(fault,))) == derive_thresholds(config)


def test_profile_without_daylight_has_no_healthy_deviation_to_derive_from():
    profile = load_bundled_profile(date(2025, 1, 15))
    night = Profile(
        timestamps=profile.timestamps[:3],
        irradiance=np.zeros(3),
        temperature=np.full(3, 20.0),
        name="night",
    )

    with pytest.raises(ValueError, match="daylight"):
        derive_thresholds(replace(bundled_run_config(), profile=night))


def test_run_summary_shows_the_site_and_the_limits():
    config = replace(
        bundled_run_config(),
        site=Site(latitude_deg=-26.2, longitude_deg=28.04, tilt_deg=10.0, azimuth_deg=180.0),
    )
    rows = dict(summary_rows(config))

    assert "latitude -26.20" in rows["Site"]
    assert "longitude 28.04" in rows["Site"]
    assert "tilt 10 deg" in rows["Site"]
    assert "5.00 %" in rows["Thresholds"]
    assert rows["Module"] == config.datasheet.name
    assert rows["Profile"].startswith("Bundled 2025-01-15")
