"""Checks and derived values for the setup of a run, before it starts. Headless, no Qt.

validate_config lists every problem with a RunConfig, so the Setup screen can report them all
without starting a run. derive_thresholds sets the warning and abnormal limits from a healthy
run. summary_rows gives the run summary that the Setup screen shows for the active run.
"""

import math
from dataclasses import replace

import numpy as np

from pvysics.datasheet import ModuleDatasheet
from pvysics.run import POWER_FLOOR_W, RunConfig, Thresholds, run
from pvysics.single_diode import fit_parameters

WARNING_SIGMAS = 2.0  # warning limit: mean + 2 standard deviations of healthy deviation
ABNORMAL_SIGMAS = 3.0  # abnormal limit: mean + 3 standard deviations
MAX_TEMPERATURE_COEFFICIENT_PCT = 5.0  # |Ki| and |Kv| above this per degree C are flagged as unreasonable


def validate_config(config: RunConfig) -> list[str]:
    """Every problem with the config, in plain words. An empty list means it can be run."""
    problems: list[str] = []
    thresholds = config.thresholds
    if not thresholds.warning_pct > 0.0:
        problems.append("The warning limit must be above 0 %.")
    if not thresholds.abnormal_pct > thresholds.warning_pct:
        problems.append("The abnormal limit must be above the warning limit.")

    mismatch = config.mismatch
    for label, offset in (("Rs", mismatch.series_resistance_pct), ("Rsh", mismatch.shunt_resistance_pct)):
        if not offset > -100.0:
            problems.append(f"The {label} offset must be above -100 %.")

    sensors = config.sensors
    noise = {
        "Irradiance noise": sensors.irradiance_noise_pct,
        "Temperature noise": sensors.temperature_noise_c,
        "Voltage noise": sensors.voltage_noise_v,
        "Current noise": sensors.current_noise_a,
        "Voltage step": sensors.voltage_step_v,
        "Current step": sensors.current_step_a,
    }
    for label, value in noise.items():
        if not (math.isfinite(value) and value >= 0.0):
            problems.append(f"{label} cannot be negative.")

    if config.seed < 0:
        problems.append("The seed must be zero or more.")

    site = config.site
    if not -90.0 <= site.latitude_deg <= 90.0:
        problems.append("Latitude must be between -90 and 90 degrees.")
    if not -180.0 <= site.longitude_deg <= 180.0:
        problems.append("Longitude must be between -180 and 180 degrees.")
    if not 0.0 <= site.tilt_deg <= 90.0:
        problems.append("Tilt must be between 0 and 90 degrees.")
    if not 0.0 <= site.azimuth_deg <= 360.0:
        problems.append("Azimuth must be between 0 and 360 degrees.")

    problems.extend(datasheet_problems(config.datasheet))
    return problems


def datasheet_problems(datasheet: ModuleDatasheet) -> list[str]:
    """Every problem with the module's values, in plain words. An empty list means the module can be modelled.

    The diode fit is tried only when the values pass the plain checks, since the fit needs positive values.
    """
    problems: list[str] = []
    for label, value in (
        ("Isc", datasheet.isc_a),
        ("Voc", datasheet.voc_v),
        ("Impp", datasheet.impp_a),
        ("Vmpp", datasheet.vmpp_v),
    ):
        if not value > 0.0:
            problems.append(f"{label} must be above zero, got {value:g}.")
    ns = datasheet.ns
    if isinstance(ns, bool) or not isinstance(ns, int) or ns < 1:
        problems.append(f"Ns must be a positive whole number of cells, got {ns!r}.")
    if _both_positive(datasheet.impp_a, datasheet.isc_a) and datasheet.impp_a >= datasheet.isc_a:
        problems.append(f"Impp must be below Isc: {datasheet.impp_a:g} A is not below {datasheet.isc_a:g} A.")
    if _both_positive(datasheet.vmpp_v, datasheet.voc_v) and datasheet.vmpp_v >= datasheet.voc_v:
        problems.append(f"Vmpp must be below Voc: {datasheet.vmpp_v:g} V is not below {datasheet.voc_v:g} V.")
    if abs(datasheet.ki_pct_per_c) > MAX_TEMPERATURE_COEFFICIENT_PCT:
        problems.append(
            f"Ki must be within {MAX_TEMPERATURE_COEFFICIENT_PCT:g} %/C either way, got {datasheet.ki_pct_per_c:g} %/C."
        )
    if datasheet.kv_pct_per_c > 0.0:
        problems.append(
            f"Kv must be zero or negative, as Voc falls with temperature, got {datasheet.kv_pct_per_c:g} %/C."
        )
    elif abs(datasheet.kv_pct_per_c) > MAX_TEMPERATURE_COEFFICIENT_PCT:
        problems.append(
            f"Kv must be within {MAX_TEMPERATURE_COEFFICIENT_PCT:g} %/C either way, got {datasheet.kv_pct_per_c:g} %/C."
        )
    if problems:
        return problems
    try:
        fit_parameters(datasheet)
    except (ValueError, ArithmeticError):  # the fit reports a failed fit as ValueError
        problems.append(f"No diode model can be fitted to {datasheet.name}: check Isc, Voc, Impp and Vmpp.")
    return problems


def _both_positive(value: float, reference: float) -> bool:
    """True when both values are above zero, so a comparison between them means something."""
    return value > 0.0 and reference > 0.0


def derive_thresholds(config: RunConfig) -> Thresholds:
    """Warning and abnormal limits from a healthy run on the config's profile, mismatch, sensors and seed.

    The limits are mean + 2 and mean + 3 standard deviations of the absolute power deviation over
    the daylight Samples, those with predicted power at or above POWER_FLOOR_W. The run has no
    faults, and the config's own thresholds do not affect it.
    """
    healthy = replace(config, faults=(), thresholds=Thresholds())
    deviations = np.array(
        [abs(sample.deviation_pct) for sample in run(healthy).samples if sample.power_predicted >= POWER_FLOOR_W]
    )
    if deviations.size == 0:
        raise ValueError("the profile has no daylight, so there is no healthy deviation to derive limits from")
    mean, sigma = float(deviations.mean()), float(deviations.std())
    return Thresholds(
        warning_pct=mean + WARNING_SIGMAS * sigma,
        abnormal_pct=mean + ABNORMAL_SIGMAS * sigma,
    )


def summary_rows(config: RunConfig) -> list[tuple[str, str]]:
    """The label and value of each line in the run summary, in the order it is shown."""
    profile, mismatch, sensors = config.profile, config.mismatch, config.sensors
    thresholds, site = config.thresholds, config.site
    first, last = profile.timestamps[0], profile.timestamps[-1]
    return [
        (
            "Profile",
            f"{profile.name or 'unnamed'}: {len(profile.timestamps)} samples from "
            f"{_stamp(first)} to {_stamp(last)}",
        ),
        ("Module", config.datasheet.name),
        ("Module values", _module_values(config.datasheet)),
        (
            "Mismatch",
            f"Rs {mismatch.series_resistance_pct:+.1f} %, Rsh {mismatch.shunt_resistance_pct:+.1f} %, "
            f"temperature coefficient {mismatch.temperature_coefficient_pct:+.1f} %",
        ),
        (
            "Sensors",
            f"noise: G {sensors.irradiance_noise_pct:g} %, T {sensors.temperature_noise_c:g} C, "
            f"V {sensors.voltage_noise_v:g} V, I {sensors.current_noise_a:g} A; "
            f"steps: V {sensors.voltage_step_v:g} V, I {sensors.current_step_a:g} A",
        ),
        ("Seed", str(config.seed)),
        ("Thresholds", f"warning {thresholds.warning_pct:.2f} %, abnormal {thresholds.abnormal_pct:.2f} %"),
        (
            "Site",
            f"latitude {site.latitude_deg:.2f}, longitude {site.longitude_deg:.2f}, "
            f"tilt {site.tilt_deg:g} deg, azimuth {site.azimuth_deg:g} deg (metadata only)",
        ),
    ]


def _module_values(datasheet: ModuleDatasheet) -> str:
    return (
        f"Isc {datasheet.isc_a:g} A, Voc {datasheet.voc_v:g} V, Impp {datasheet.impp_a:g} A, "
        f"Vmpp {datasheet.vmpp_v:g} V, Ki {datasheet.ki_pct_per_c:g} %/C, "
        f"Kv {datasheet.kv_pct_per_c:g} %/C, Ns {datasheet.ns}"
    )


def _stamp(stamp: np.datetime64) -> str:
    return np.datetime_as_string(stamp, unit="m").replace("T", " ")
