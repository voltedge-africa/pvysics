import subprocess
import sys
from dataclasses import replace

import numpy as np
import pytest

from pvysics.run import (
    POWER_FLOOR_W,
    Mismatch,
    RunConfig,
    SensorModel,
    Site,
    State,
    Thresholds,
    bundled_run_config,
    run,
)

NO_NOISE = SensorModel(
    irradiance_noise_pct=0.0,
    temperature_noise_c=0.0,
    voltage_noise_v=0.0,
    current_noise_a=0.0,
    voltage_step_v=0.0,
    current_step_a=0.0,
)
NO_MISMATCH = Mismatch(
    series_resistance_pct=0.0, shunt_resistance_pct=0.0, temperature_coefficient_pct=0.0
)
COARSE_STEP_S = 600.0  # 10 minutes: keeps the suite fast; default is 1 minute


def configured(**changes) -> RunConfig:
    """The bundled Durban day at a coarse step, with the given fields replaced."""
    return replace(bundled_run_config(seed=1), time_step_s=COARSE_STEP_S, **changes)


def daylight(result):
    return [sample for sample in result.samples if sample.power_predicted >= POWER_FLOOR_W]


def max_abs_deviation(result):
    return max(abs(sample.deviation_pct) for sample in daylight(result))


def test_healthy_bundled_run_stays_normal_with_small_nonzero_deviation():
    result = run(bundled_run_config(seed=0))

    assert all(sample.state is State.NORMAL for sample in result.samples)
    assert result.events == []
    assert 0.0 < max_abs_deviation(result) < 5.0


def test_zero_mismatch_and_zero_noise_gives_zero_deviation():
    result = run(configured(mismatch=NO_MISMATCH, sensors=NO_NOISE))

    assert daylight(result)
    assert max_abs_deviation(result) < 1e-9


def test_power_measured_is_measured_voltage_times_measured_current():
    result = run(configured())

    for sample in result.samples:
        assert sample.power_measured == sample.measured_voltage * sample.measured_current


def test_mismatch_alone_gives_visible_deviation():
    result = run(configured(sensors=NO_NOISE))

    assert max_abs_deviation(result) > 0.01


def test_noise_alone_gives_visible_deviation():
    result = run(configured(mismatch=NO_MISMATCH))

    assert max_abs_deviation(result) > 0.1


def test_same_seed_gives_identical_results():
    first = run(configured(seed=7))
    second = run(configured(seed=7))

    assert first.samples == second.samples
    assert first.events == second.events


def test_different_seed_changes_the_noise_but_not_the_profile():
    first = run(configured(seed=7))
    second = run(configured(seed=8))

    assert [s.true_irradiance for s in first.samples] == [s.true_irradiance for s in second.samples]
    assert [s.measured_irradiance for s in first.samples] != [
        s.measured_irradiance for s in second.samples
    ]


def test_night_samples_have_no_deviation_and_no_state_flapping():
    result = run(bundled_run_config(seed=0))

    night = [sample for sample in result.samples if sample.power_predicted < POWER_FLOOR_W]
    assert night
    assert all(sample.deviation_pct == 0.0 for sample in night)
    assert all(sample.state is State.NORMAL for sample in night)
    daylight_stamps = {sample.timestamp for sample in daylight(result)}
    assert all(event.timestamp in daylight_stamps for event in result.events)


def test_state_changes_are_emitted_as_timestamped_events():
    tight = Thresholds(warning_pct=0.5, abnormal_pct=1.0)
    result = run(configured(thresholds=tight))

    changes = [
        (later.timestamp, later.state)
        for earlier, later in zip(result.samples, result.samples[1:])
        if earlier.state is not later.state
    ]
    assert changes
    assert [event.timestamp for event in result.events] == [stamp for stamp, _ in changes]
    assert all(event.kind == "state" for event in result.events)
    assert all(event.detail for event in result.events)


def test_irradiance_is_never_negative_even_with_large_sensor_noise():
    noisy = replace(NO_NOISE, irradiance_noise_pct=200.0)
    result = run(configured(sensors=noisy))

    assert all(sample.measured_irradiance >= 0.0 for sample in result.samples)
    assert all(sample.true_irradiance >= 0.0 for sample in result.samples)


def test_time_step_sets_sample_spacing_and_interpolates_linearly():
    result = run(configured(mismatch=NO_MISMATCH, sensors=NO_NOISE))

    stamps = np.array([sample.timestamp for sample in result.samples])
    assert np.all(np.diff(stamps) == np.timedelta64(600, "s"))
    assert stamps[0] == np.datetime64("2025-01-15T00:00:00")
    assert stamps[-1] == np.datetime64("2025-01-15T23:00:00")
    index_1130 = 11 * 6 + 3  # six 10-minute steps per hour, plus three for :30
    sample = result.samples[index_1130]
    assert sample.timestamp == np.datetime64("2025-01-15T11:30:00")
    irradiance = bundled_run_config(seed=1).profile.irradiance
    assert sample.true_irradiance == pytest.approx((irradiance[11] + irradiance[12]) / 2.0)


def test_run_api_imports_without_qt():
    code = (
        "import sys, pvysics.run; "
        "assert not any(m.startswith('PyQt') for m in sys.modules)"
    )

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_site_is_stored_with_the_run_and_does_not_change_the_samples():
    site = Site(latitude_deg=-26.2, longitude_deg=28.04, tilt_deg=10.0, azimuth_deg=180.0)

    durban = run(configured())
    elsewhere = run(configured(site=site))

    assert elsewhere.config.site == site
    assert elsewhere.samples == durban.samples


def test_site_defaults_to_durban():
    assert Site() == Site(latitude_deg=-29.85, longitude_deg=31.00, tilt_deg=26.0, azimuth_deg=0.0)
    assert bundled_run_config().site == Site()
