"""Headless run: a Profile drives the plant and the twin, giving Samples, Events and States.

No Qt imports: tests, scripts and a later ESP32 feed all call this module directly.

Power deviation = (P measured - P predicted) / P predicted * 100.
Positive means the plant makes more power than the twin predicts; negative means less.
Below POWER_FLOOR_W of predicted power the deviation is 0 and the State is Normal,
so night-time cannot raise a false alarm.
"""

from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from pvysics.datasheet import ModuleDatasheet, load_generic_datasheet
from pvysics.profile import Profile, load_bundled_profile
from pvysics.single_diode import DiodeParameters, fit_parameters, solve_curve

BUNDLED_DAY = date(2025, 1, 15)
POWER_FLOOR_W = 5.0  # predicted power below this gives no deviation
NOISE_CHANNELS = 4  # irradiance, temperature, voltage, current


class State(Enum):
    NORMAL = "Normal"
    WARNING = "Warning"
    ABNORMAL = "Abnormal"


@dataclass(frozen=True)
class Mismatch:
    """Plant offsets from the datasheet, as percent of the nominal value."""

    series_resistance_pct: float = 3.0
    shunt_resistance_pct: float = 5.0
    temperature_coefficient_pct: float = 2.0  # applied to Kv, the Voc coefficient


@dataclass(frozen=True)
class SensorModel:
    """Noise (standard deviations) and quantisation (step sizes; 0 means none)."""

    # Relative per-sample noise. A 3 percent per-sample sd makes a healthy run flap between
    # Warning and Abnormal, so the 3 percent sensor accuracy is modelled as 0.5 percent noise.
    irradiance_noise_pct: float = 0.5
    temperature_noise_c: float = 0.5  # DS18B20
    voltage_noise_v: float = 0.002
    current_noise_a: float = 0.0001
    voltage_step_v: float = 0.004  # INA219 bus voltage LSB
    current_step_a: float = 0.0001  # INA219 current LSB, 0.1 mA


@dataclass(frozen=True)
class Thresholds:
    """Power deviation limits in percent of absolute deviation."""

    warning_pct: float = 5.0
    abnormal_pct: float = 10.0


@dataclass(frozen=True)
class RunConfig:
    profile: Profile
    datasheet: ModuleDatasheet
    mismatch: Mismatch = Mismatch()
    sensors: SensorModel = SensorModel()
    thresholds: Thresholds = Thresholds()
    seed: int = 0
    time_step_s: float = 60.0


@dataclass(frozen=True)
class Sample:
    timestamp: np.datetime64
    true_irradiance: float  # W/m^2
    true_temperature: float  # degrees C
    measured_irradiance: float  # W/m^2, seen by the twin
    measured_temperature: float  # degrees C, seen by the twin
    measured_voltage: float  # V, from the plant sensors
    measured_current: float  # A, from the plant sensors
    power_measured: float  # W
    power_predicted: float  # W
    deviation_pct: float
    state: State


@dataclass(frozen=True)
class Event:
    timestamp: np.datetime64
    kind: str  # "state" for a state change
    detail: str


@dataclass(frozen=True)
class RunResult:
    config: RunConfig
    samples: list[Sample] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


def bundled_run_config(seed: int = 0) -> RunConfig:
    """The bundled Durban day on the generic module, with default mismatch, sensors and thresholds."""
    return RunConfig(
        profile=load_bundled_profile(BUNDLED_DAY),
        datasheet=load_generic_datasheet(),
        seed=seed,
    )


def run(config: RunConfig) -> RunResult:
    """Run the profile through the plant and the twin, one Sample per time step.

    The plant runs at its maximum power point for the true G and T, read through noisy,
    quantised sensors. The twin predicts power from the measured G and T with nominal
    datasheet parameters. All randomness comes from one generator seeded by config.seed.
    """
    if config.time_step_s <= 0.0:
        raise ValueError("time_step_s must be positive")
    if config.thresholds.warning_pct >= config.thresholds.abnormal_pct:
        raise ValueError("warning_pct must be below abnormal_pct")

    offsets_s, true_g, true_t = _interpolate(config.profile, config.time_step_s)
    noise = np.random.default_rng(config.seed).standard_normal((len(offsets_s), NOISE_CHANNELS))
    plant_datasheet, plant_parameters = _plant(config)
    origin = config.profile.timestamps[0]

    samples: list[Sample] = []
    events: list[Event] = []
    for k, offset in enumerate(offsets_s):
        stamp = origin + np.timedelta64(round(offset), "s")
        sample = _sample(
            stamp, true_g[k], true_t[k], noise[k], config, plant_datasheet, plant_parameters
        )
        if samples and sample.state is not samples[-1].state:
            events.append(
                Event(stamp, "state", f"{samples[-1].state.value} -> {sample.state.value}")
            )
        samples.append(sample)
    return RunResult(config=config, samples=samples, events=events)


def _interpolate(
    profile: Profile, step_s: float
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Linear interpolation of the profile onto a grid of step_s, with irradiance clipped at 0."""
    hours_s = (profile.timestamps - profile.timestamps[0]) / np.timedelta64(1, "s")
    offsets_s = np.arange(0.0, hours_s[-1] + 1e-9, step_s)
    irradiance = np.maximum(np.interp(offsets_s, hours_s, profile.irradiance), 0.0)
    temperature = np.interp(offsets_s, hours_s, profile.temperature)
    return offsets_s, irradiance, temperature


def _plant(config: RunConfig) -> tuple[ModuleDatasheet, DiodeParameters]:
    """The plant's datasheet and parameters: the nominal fit with the mismatch applied."""
    nominal = fit_parameters(config.datasheet)
    mismatch = config.mismatch
    parameters = replace(
        nominal,
        series_resistance_ohm=nominal.series_resistance_ohm
        * (1.0 + mismatch.series_resistance_pct / 100.0),
        shunt_resistance_ohm=nominal.shunt_resistance_ohm
        * (1.0 + mismatch.shunt_resistance_pct / 100.0),
    )
    datasheet = replace(
        config.datasheet,
        kv_pct_per_c=config.datasheet.kv_pct_per_c
        * (1.0 + mismatch.temperature_coefficient_pct / 100.0),
    )
    return datasheet, parameters


def _sample(
    stamp: np.datetime64,
    true_g: float,
    true_t: float,
    noise: NDArray[np.float64],
    config: RunConfig,
    plant_datasheet: ModuleDatasheet,
    plant_parameters: DiodeParameters,
) -> Sample:
    sensors = config.sensors
    plant = solve_curve(plant_datasheet, true_g, true_t, plant_parameters)
    measured_g = max(0.0, true_g * (1.0 + sensors.irradiance_noise_pct / 100.0 * noise[0]))
    measured_t = true_t + sensors.temperature_noise_c * noise[1]
    measured_v = _quantise(
        plant.mpp_voltage + sensors.voltage_noise_v * noise[2], sensors.voltage_step_v
    )
    measured_i = _quantise(
        plant.mpp_current + sensors.current_noise_a * noise[3], sensors.current_step_a
    )
    power_measured = measured_v * measured_i
    power_predicted = solve_curve(config.datasheet, measured_g, measured_t).mpp_power

    deviation = 0.0
    if power_predicted >= POWER_FLOOR_W:
        deviation = (power_measured - power_predicted) / power_predicted * 100.0
    return Sample(
        timestamp=stamp,
        true_irradiance=true_g,
        true_temperature=true_t,
        measured_irradiance=measured_g,
        measured_temperature=measured_t,
        measured_voltage=measured_v,
        measured_current=measured_i,
        power_measured=power_measured,
        power_predicted=power_predicted,
        deviation_pct=deviation,
        state=_state(deviation, config.thresholds),
    )


def _state(deviation_pct: float, thresholds: Thresholds) -> State:
    """Abnormal above the abnormal limit, Warning above the warning limit, else Normal."""
    magnitude = abs(deviation_pct)
    if magnitude > thresholds.abnormal_pct:
        return State.ABNORMAL
    if magnitude > thresholds.warning_pct:
        return State.WARNING
    return State.NORMAL


def _quantise(value: float, step: float) -> float:
    if step <= 0.0:
        return value
    return float(np.round(value / step) * step)
