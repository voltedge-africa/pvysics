"""Setup checks, derived thresholds and the run summary. Headless: no GUI."""

from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from pvysics.datasheet import edited_datasheet, load_generic_datasheet
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
from pvysics.run_setup import datasheet_problems, derive_thresholds, summary_rows, validate_config


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


GENERIC = load_generic_datasheet()


def test_generic_datasheet_has_no_problems():
    assert datasheet_problems(GENERIC) == []


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"isc_a": 0.0}, "Isc must be above zero"),
        ({"voc_v": -1.0}, "Voc must be above zero"),
        ({"impp_a": 0.0}, "Impp must be above zero"),
        ({"vmpp_v": 0.0}, "Vmpp must be above zero"),
        ({"ns": 0}, "Ns must be a positive whole number"),
        ({"ns": 2.5}, "Ns must be a positive whole number"),
        ({"vmpp_v": 37.8}, "Vmpp must be below Voc"),
        ({"vmpp_v": 40.0}, "Vmpp must be below Voc"),
        ({"impp_a": 8.9}, "Impp must be below Isc"),
        ({"ki_pct_per_c": 6.0}, "Ki must be within 5 %/C"),
        ({"ki_pct_per_c": -6.0}, "Ki must be within 5 %/C"),
        ({"kv_pct_per_c": 0.3}, "Kv must be zero or negative"),
        ({"kv_pct_per_c": -6.0}, "Kv must be within 5 %/C"),
        ({"vmpp_v": 11.3, "impp_a": 8.8}, "No diode model can be fitted"),
    ],
)
def test_each_invalid_datasheet_value_gives_its_own_message(values, message):
    problems = datasheet_problems(edited_datasheet(GENERIC, **values))

    assert len(problems) == 1
    assert message in problems[0]


def test_every_datasheet_problem_is_listed_at_once():
    problems = datasheet_problems(edited_datasheet(GENERIC, isc_a=0.0, vmpp_v=40.0))

    assert any("Isc must be above zero" in problem for problem in problems)
    assert any("Vmpp must be below Voc" in problem for problem in problems)


def test_validate_config_reports_a_datasheet_problem():
    config = replace(bundled_run_config(), datasheet=edited_datasheet(GENERIC, impp_a=9.0))

    assert any("Impp must be below Isc" in problem for problem in validate_config(config))


def test_run_summary_shows_the_edited_module_values():
    config = replace(
        bundled_run_config(), datasheet=edited_datasheet(GENERIC, isc_a=9.3, ns=72)
    )

    rows = dict(summary_rows(config))

    assert rows["Module"] == "Custom module"
    assert "Isc 9.3 A" in rows["Module values"]
    assert "Ns 72" in rows["Module values"]
