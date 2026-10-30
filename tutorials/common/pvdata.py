"""Real numbers for the tutorials: every curve and figure on screen comes from the app's own engine (src/pvysics).

No Manim here, so the figures can be checked from a plain script:   tutorials/.venv/bin/python tutorials/common/pvdata.py

    module()                            the generic 60-cell 250 W datasheet
    iv(g, t, datasheet)                 I-V and P-V curves, and the maximum power point
    fault_iv(kind, ...)                 the plant's curve with one fault on, next to the healthy one
    day(fault=None, fault_hour=11.0)    one simulated day: hours, measured and predicted power, deviation, state
"""

import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pvysics.datasheet import load_generic_datasheet  # noqa: E402
from pvysics.faults import FaultKind, ScheduledFault, apply_faults, default_fault  # noqa: E402
from pvysics.run import bundled_run_config, run  # noqa: E402
from pvysics.single_diode import fit_parameters, solve_curve  # noqa: E402

__all__ = ["FaultKind", "module", "iv", "fault_iv", "day", "DayData", "diode_parameters", "default_fault"]


def module():
    """The generic 60-cell, 250 W datasheet (Isc 8.9 A, Voc 37.8 V, Impp 8.3 A, Vmpp 30.1 V)."""
    return load_generic_datasheet()


def diode_parameters(datasheet=None):
    """Iph, Rs, Rsh and n fitted so the STC curve has the datasheet's Isc and maximum power point."""
    return fit_parameters(datasheet or module())


def iv(g: float, t: float, datasheet=None):
    """The twin's curves for irradiance g (W/m2) and cell temperature t (deg C)."""
    return solve_curve(datasheet or module(), g, t)


def fault_iv(kind: FaultKind, g: float = 1000.0, t: float = 25.0, severity: float | None = None):
    """(healthy, faulty) curves at g and t. The fault changes the plant, as in the app's default strength."""
    datasheet = module()
    healthy = solve_curve(datasheet, g, t)
    fault = default_fault(kind) if severity is None else replace(default_fault(kind), severity=severity)
    effect = apply_faults({kind: fault.severity}, datasheet, fit_parameters(datasheet))
    faulty = solve_curve(effect.datasheet, g * effect.irradiance_scale, t, effect.parameters)
    return healthy, faulty


@dataclass(frozen=True)
class DayData:
    hours: np.ndarray
    measured: np.ndarray
    predicted: np.ndarray
    deviation: np.ndarray
    state: list[str]
    irradiance: np.ndarray
    temperature: np.ndarray
    voltage: np.ndarray
    current: np.ndarray


def day(fault: FaultKind | None = None, fault_hour: float = 11.0, seed: int = 1) -> DayData:
    """The bundled Durban day, run through plant and twin. A fault, if given, starts at fault_hour and stays on."""
    config = bundled_run_config(seed=seed)
    if fault is not None:
        start = config.profile.timestamps[0] + np.timedelta64(int(fault_hour * 3600), "s")
        config = replace(config, faults=(ScheduledFault(default_fault(fault), start),))
    samples = run(config).samples
    origin = samples[0].timestamp
    hours = np.array([(s.timestamp - origin) / np.timedelta64(1, "h") for s in samples])
    return DayData(
        hours=hours,
        measured=np.array([s.power_measured for s in samples]),
        predicted=np.array([s.power_predicted for s in samples]),
        deviation=np.array([s.deviation_pct for s in samples]),
        state=[s.state.value for s in samples],
        irradiance=np.array([s.measured_irradiance for s in samples]),
        temperature=np.array([s.measured_temperature for s in samples]),
        voltage=np.array([s.measured_voltage for s in samples]),
        current=np.array([s.measured_current for s in samples]),
    )


if __name__ == "__main__":
    d = module()
    p = diode_parameters()
    print(f"module: {d.name}, Ns {d.ns}, Isc {d.isc_a}, Voc {d.voc_v}, Impp {d.impp_a}, Vmpp {d.vmpp_v}")
    print(f"fit: Iph {p.photocurrent_stc_a:.3f} A, Rs {p.series_resistance_ohm:.3f} ohm, Rsh {p.shunt_resistance_ohm:.0f} ohm, n {p.ideality}")
    for g, t in ((1000, 25), (800, 25), (500, 25), (200, 25), (1000, 45), (1000, 65)):
        c = iv(g, t)
        print(f"G {g:4d} T {t:2d}: Isc {c.current[0]:.2f} A  Voc {c.voltage[-1]:.1f} V  Pmpp {c.mpp_power:.1f} W at {c.mpp_voltage:.1f} V {c.mpp_current:.2f} A")
    for kind in FaultKind:
        h, f = fault_iv(kind)
        print(f"{kind.value:24s}: Pmpp {h.mpp_power:.1f} -> {f.mpp_power:.1f} W ({(f.mpp_power - h.mpp_power) / h.mpp_power * 100:+.1f} %), Voc {f.voltage[-1]:.1f} V, Isc {f.current[0]:.2f} A")
    base = day()
    print(f"healthy day: peak measured {base.measured.max():.1f} W at hour {base.hours[base.measured.argmax()]:.1f}, "
          f"max |deviation| in daylight {np.abs(base.deviation[base.predicted >= 5]).max():.2f} %, states {sorted(set(base.state))}")
    for kind in FaultKind:
        x = day(kind)
        after = (x.hours >= 11.5) & (x.predicted >= 5)
        print(f"{kind.value:24s}: mean deviation after 11:30 {x.deviation[after].mean():+.1f} %, states {sorted(set(x.state[i] for i in np.where(after)[0]))}")
