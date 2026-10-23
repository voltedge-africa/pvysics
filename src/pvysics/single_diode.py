"""Single Diode Model: the physics core of the twin and the plant. Headless, no Qt.

Circuit: I = Iph - I0*(exp((V + I*Rs)/(n*Ns*Vt)) - 1) - (V + I*Rs)/Rsh
with Vt = k*Tcell/q. Iph scales with irradiance and temperature (Isc and Ki),
I0 is set from Voc with its temperature shift (Kv), and Rs and Rsh are fitted
at standard test conditions so the curve reproduces the datasheet MPP.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares

from pvysics.datasheet import ModuleDatasheet

BOLTZMANN = 1.380649e-23  # J/K
ELEMENTARY_CHARGE = 1.602176634e-19  # C
KELVIN_OFFSET = 273.15
STC_IRRADIANCE = 1000.0  # W/m^2
STC_TEMPERATURE = 25.0  # degrees C
DEFAULT_IDEALITY = 1.3
CURVE_POINTS = 500
MPP_SLOPE_STEP = 1e-4  # V, half-width of the finite difference at the MPP
FIT_TOLERANCE = 1e-3  # relative residual accepted from the parameter fit
BISECTION_STEPS = 100


@dataclass(frozen=True)
class DiodeParameters:
    """Circuit parameters at standard test conditions. Override fields to perturb a plant."""

    ideality: float  # n
    photocurrent_stc_a: float  # Iph at 1000 W/m^2 and 25 C
    series_resistance_ohm: float  # Rs
    shunt_resistance_ohm: float  # Rsh


@dataclass(frozen=True)
class IVCurve:
    """I-V and P-V curves from 0 V to open circuit, with the maximum power point."""

    voltage: NDArray[np.float64]  # V
    current: NDArray[np.float64]  # A
    power: NDArray[np.float64]  # W
    mpp_voltage: float
    mpp_current: float
    mpp_power: float


@lru_cache(maxsize=None)
def fit_parameters(
    datasheet: ModuleDatasheet, ideality: float = DEFAULT_IDEALITY
) -> DiodeParameters:
    """Fit Iph, Rs and Rsh so the STC curve has the datasheet Isc and MPP, with I0 set by Voc.

    The MPP is pinned by its current and by zero slope in power, so it is a maximum.
    """
    thermal = _thermal_voltage(datasheet.ns, STC_TEMPERATURE, ideality)
    isc, voc = datasheet.isc_a, datasheet.voc_v
    vmpp, impp = datasheet.vmpp_v, datasheet.impp_a

    def residuals(x: NDArray[np.float64]) -> NDArray[np.float64]:
        iph, rs, rsh = x
        i0 = _saturation_current(iph, voc, thermal, rsh)
        short_circuit = _current(np.zeros(1), iph, i0, thermal, rs, rsh)[0]
        at_mpp = _current(np.array([vmpp]), iph, i0, thermal, rs, rsh)[0]
        around = np.array([vmpp - MPP_SLOPE_STEP, vmpp + MPP_SLOPE_STEP])
        power = around * _current(around, iph, i0, thermal, rs, rsh)
        slope = (power[1] - power[0]) / (2.0 * MPP_SLOPE_STEP)
        return np.array([(short_circuit - isc) / isc, (at_mpp - impp) / impp, slope / impp])

    fit = least_squares(
        residuals,
        x0=[isc, 0.3, 200.0],
        bounds=([0.5 * isc, 1e-4, 1.0], [2.0 * isc, 10.0, 1e6]),
        xtol=1e-14,
        ftol=1e-14,
        gtol=1e-14,
    )
    if not fit.success or np.max(np.abs(fit.fun)) > FIT_TOLERANCE:
        raise ValueError(f"cannot fit diode parameters to {datasheet.name}")
    iph, rs, rsh = fit.x
    return DiodeParameters(
        ideality=ideality,
        photocurrent_stc_a=float(iph),
        series_resistance_ohm=float(rs),
        shunt_resistance_ohm=float(rsh),
    )


def solve_curve(
    datasheet: ModuleDatasheet,
    irradiance: float,
    temperature: float,
    parameters: DiodeParameters | None = None,
) -> IVCurve:
    """I-V and P-V curves for one module at irradiance (W/m^2) and cell temperature (degrees C).

    Pass `parameters` to run a perturbed plant; the default is the fit to the datasheet.
    Datasheet Ki and Kv (replace them with dataclasses.replace) shift Isc and Voc with temperature.
    """
    if parameters is None:
        parameters = fit_parameters(datasheet)
    thermal = _thermal_voltage(datasheet.ns, temperature, parameters.ideality)
    shift = temperature - STC_TEMPERATURE
    iph_scale = 1.0 + datasheet.ki_pct_per_c / 100.0 * shift
    iph_at_temperature = parameters.photocurrent_stc_a * iph_scale
    voc = datasheet.voc_v * (1.0 + datasheet.kv_pct_per_c / 100.0 * shift)
    rs = parameters.series_resistance_ohm
    rsh = parameters.shunt_resistance_ohm
    i0 = _saturation_current(iph_at_temperature, voc, thermal, rsh)
    iph = iph_at_temperature * irradiance / STC_IRRADIANCE

    open_circuit = _open_circuit_voltage(iph, i0, thermal, rsh)
    voltage = np.linspace(0.0, open_circuit, CURVE_POINTS)
    current = _current(voltage, iph, i0, thermal, rs, rsh)
    power = voltage * current
    peak = int(np.argmax(power))
    return IVCurve(
        voltage=voltage,
        current=current,
        power=power,
        mpp_voltage=float(voltage[peak]),
        mpp_current=float(current[peak]),
        mpp_power=float(power[peak]),
    )


def _thermal_voltage(ns: int, temperature: float, ideality: float) -> float:
    """n*Ns*Vt: the diode voltage scale of a whole module."""
    kelvin = temperature + KELVIN_OFFSET
    return ideality * ns * BOLTZMANN * kelvin / ELEMENTARY_CHARGE


def _saturation_current(isc: float, voc: float, thermal: float, rsh: float) -> float:
    """I0 such that the curve with photocurrent Isc has open-circuit voltage Voc."""
    return (isc - voc / rsh) / np.expm1(voc / thermal)


def _open_circuit_voltage(iph: float, i0: float, thermal: float, rsh: float) -> float:
    """Voltage where the current is zero (Rs carries no current there)."""
    def residual(voltage: NDArray[np.float64]) -> NDArray[np.float64]:
        return iph - i0 * np.expm1(voltage / thermal) - voltage / rsh

    upper = thermal * np.log1p(iph / i0)
    return float(_bisect(residual, np.zeros(()), np.asarray(upper)))


def _current(
    voltage: NDArray[np.float64], iph: float, i0: float, thermal: float, rs: float, rsh: float
) -> NDArray[np.float64]:
    """Terminal current at each voltage. The implicit equation has one root in [0, Iph]."""
    def residual(current: NDArray[np.float64]) -> NDArray[np.float64]:
        diode_voltage = voltage + current * rs
        return iph - i0 * np.expm1(diode_voltage / thermal) - diode_voltage / rsh - current

    lower = np.zeros_like(voltage)
    upper = np.full_like(voltage, iph)
    return _bisect(residual, lower, upper)


def _bisect(
    residual: Callable[[NDArray[np.float64]], NDArray[np.float64]],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Vectorised bisection for the root of a decreasing function. Always converges."""
    for _ in range(BISECTION_STEPS):
        middle = 0.5 * (lower + upper)
        above_root = residual(middle) > 0.0
        lower = np.where(above_root, middle, lower)
        upper = np.where(above_root, upper, middle)
    return 0.5 * (lower + upper)
