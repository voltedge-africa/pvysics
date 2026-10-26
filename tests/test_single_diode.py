import subprocess
import sys
from dataclasses import replace

import numpy as np
import pytest

from pvysics.datasheet import edited_datasheet, load_generic_datasheet
from pvysics.single_diode import fit_parameters, solve_curve

DATASHEET = load_generic_datasheet()


def test_stc_curve_reproduces_datasheet_isc_voc_and_pmpp():
    curve = solve_curve(DATASHEET, 1000.0, 25.0)

    assert curve.current[0] == pytest.approx(DATASHEET.isc_a, rel=0.02)
    assert curve.voltage[-1] == pytest.approx(DATASHEET.voc_v, rel=0.02)
    assert curve.current[-1] == pytest.approx(0.0, abs=1e-3)
    assert curve.mpp_power == pytest.approx(DATASHEET.pmpp_w, rel=0.02)


def test_mpp_is_the_highest_point_on_the_power_curve():
    curve = solve_curve(DATASHEET, 1000.0, 25.0)

    assert curve.mpp_power == pytest.approx(np.max(curve.power))
    assert curve.mpp_power == pytest.approx(curve.mpp_voltage * curve.mpp_current)


def test_power_rises_with_irradiance():
    irradiances = [200.0, 400.0, 600.0, 800.0, 1000.0]

    powers = [solve_curve(DATASHEET, g, 25.0).mpp_power for g in irradiances]

    assert all(later > earlier for earlier, later in zip(powers, powers[1:]))


def test_power_falls_with_cell_temperature():
    temperatures = [0.0, 25.0, 50.0, 75.0]

    powers = [solve_curve(DATASHEET, 1000.0, t).mpp_power for t in temperatures]

    assert all(later < earlier for earlier, later in zip(powers, powers[1:]))


def test_zero_irradiance_gives_zero_power_without_nan():
    curve = solve_curve(DATASHEET, 0.0, 25.0)

    assert np.all(np.isfinite(curve.current))
    assert np.all(np.isfinite(curve.power))
    assert np.all(curve.power == 0.0)
    assert curve.mpp_power == 0.0


@pytest.mark.parametrize(
    ("irradiance", "temperature"),
    [(1000.0, 25.0), (1000.0, 70.0), (300.0, 0.0), (50.0, 25.0), (1200.0, 60.0)],
)
def test_full_voltage_sweep_converges_from_zero_to_open_circuit(irradiance, temperature):
    curve = solve_curve(DATASHEET, irradiance, temperature)

    assert curve.voltage[0] == 0.0
    assert np.all(np.isfinite(curve.current))
    assert np.all(np.diff(curve.voltage) > 0.0)
    assert np.all(np.diff(curve.current) <= 1e-9)  # current falls as voltage rises
    assert np.all(curve.current >= -1e-6)
    assert curve.current[-1] == pytest.approx(0.0, abs=1e-3)


def test_overriding_series_resistance_lowers_the_plant_power():
    nominal = fit_parameters(DATASHEET)
    raised = replace(nominal, series_resistance_ohm=2.0 * nominal.series_resistance_ohm)

    nominal_power = solve_curve(DATASHEET, 1000.0, 25.0, nominal).mpp_power
    plant_power = solve_curve(DATASHEET, 1000.0, 25.0, raised).mpp_power

    assert plant_power < nominal_power


def test_overriding_shunt_resistance_changes_the_curve():
    nominal = fit_parameters(DATASHEET)
    leaky = replace(nominal, shunt_resistance_ohm=nominal.shunt_resistance_ohm / 10.0)

    nominal_curve = solve_curve(DATASHEET, 1000.0, 25.0, nominal)
    leaky_curve = solve_curve(DATASHEET, 1000.0, 25.0, leaky)

    assert leaky_curve.mpp_power < nominal_curve.mpp_power


def test_overriding_temperature_coefficient_changes_the_hot_power():
    hot = 60.0
    steeper = replace(DATASHEET, kv_pct_per_c=DATASHEET.kv_pct_per_c * 2.0)

    nominal_power = solve_curve(DATASHEET, 1000.0, hot).mpp_power
    plant_power = solve_curve(steeper, 1000.0, hot).mpp_power

    assert plant_power < nominal_power


def test_engine_imports_without_qt():
    code = (
        "import sys, pvysics.single_diode; "
        "assert not any(m.startswith('PyQt') for m in sys.modules)"
    )

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_edited_module_stc_power_matches_its_pmpp():
    edited = edited_datasheet(DATASHEET, isc_a=9.3, voc_v=38.5, impp_a=8.6, vmpp_v=29.0)

    curve = solve_curve(edited, 1000.0, 25.0)

    assert curve.current[0] == pytest.approx(edited.isc_a, rel=0.02)
    assert curve.voltage[-1] == pytest.approx(edited.voc_v, rel=0.02)
    assert curve.mpp_power == pytest.approx(edited.pmpp_w, rel=0.02)


def test_the_bundled_generic_module_fits():
    parameters = fit_parameters(DATASHEET)

    assert parameters.photocurrent_stc_a > 0
    assert parameters.series_resistance_ohm > 0
    assert parameters.shunt_resistance_ohm > 0


def test_the_bundled_run_starts_the_plant_the_app_opens_with():
    from pvysics.run import Simulation, bundled_run_config

    Simulation(bundled_run_config())  # builds the plant, which fits the generic module: this is what failed at launch


def test_a_fit_with_small_residuals_is_accepted_whatever_status_scipy_reports(monkeypatch):
    # On one machine SciPy stopped on its evaluation cap (success False, status 0) with residuals ~2e-5.
    from pvysics import single_diode

    real = single_diode.least_squares

    def capped(*args, **kwargs):
        fit = real(*args, **kwargs)
        fit.success, fit.status = False, 0
        return fit

    monkeypatch.setattr(single_diode, "least_squares", capped)
    fit_parameters.cache_clear()
    try:
        assert fit_parameters(DATASHEET).photocurrent_stc_a > 0
    finally:
        fit_parameters.cache_clear()


def test_a_fit_with_large_residuals_is_refused_with_the_reason(monkeypatch):
    from pvysics import single_diode

    real = single_diode.least_squares

    def failed(*args, **kwargs):
        fit = real(*args, **kwargs)
        fit.fun = fit.fun + 0.5
        return fit

    monkeypatch.setattr(single_diode, "least_squares", failed)
    fit_parameters.cache_clear()
    try:
        with pytest.raises(ValueError, match="max residual"):
            fit_parameters(DATASHEET)
    finally:
        fit_parameters.cache_clear()
