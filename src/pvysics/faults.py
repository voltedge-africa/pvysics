"""Faults: injected plant conditions, scheduled or live. Headless, no Qt.

Each fault has one severity, in the unit given by its kind:
- partial shading: fraction of the photocurrent lost, 0 to 1.
- soiling: fraction of the irradiance lost, 0 to 1.
- series-resistance rise: fractional rise in Rs, 0 or more (1.0 doubles Rs).
- bypass-diode failure: fraction of the series cells bypassed, 0 to below 1.
- sensor drift: bias on the measured irradiance seen by the twin, fraction of true G,
  positive reads high, any value above -1.

Shading and soiling both scale the photocurrent through the irradiance. In the Single Diode
Model they are therefore the same effect; they stay separate kinds because the operator
names them differently.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum

import numpy as np

from pvysics.datasheet import ModuleDatasheet
from pvysics.single_diode import DiodeParameters


class FaultKind(Enum):
    PARTIAL_SHADING = "partial shading"
    SOILING = "soiling"
    SERIES_RESISTANCE_RISE = "series-resistance rise"
    DIODE_FAILURE = "bypass-diode failure"
    SENSOR_DRIFT = "sensor drift"


DEFAULT_SEVERITY = {
    FaultKind.PARTIAL_SHADING: 0.3,
    FaultKind.SOILING: 0.2,
    FaultKind.SERIES_RESISTANCE_RISE: 6.0,  # Rs about seven times nominal
    FaultKind.DIODE_FAILURE: 1.0 / 3.0,  # one of three groups of cells
    FaultKind.SENSOR_DRIFT: 0.15,
}


@dataclass(frozen=True)
class Fault:
    kind: FaultKind
    severity: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.severity) or not _severity_is_valid(self.kind, self.severity):
            raise ValueError(f"invalid severity {self.severity} for {self.kind.value}")


@dataclass(frozen=True)
class ScheduledFault:
    """A fault that is active from start, until end if given (end is exclusive)."""

    fault: Fault
    start: np.datetime64
    end: np.datetime64 | None = None


@dataclass(frozen=True)
class PlantEffect:
    """What the active faults do to the plant and to the sensor the twin reads."""

    datasheet: ModuleDatasheet
    parameters: DiodeParameters
    irradiance_scale: float  # the plant receives the true irradiance times this
    sensor_bias: float  # the measured irradiance reads the true irradiance times (1 + this)


def default_fault(kind: FaultKind) -> Fault:
    return Fault(kind, DEFAULT_SEVERITY[kind])


def apply_faults(
    severities: Mapping[FaultKind, float],
    datasheet: ModuleDatasheet,
    parameters: DiodeParameters,
) -> PlantEffect:
    """The plant and sensor effect of the active faults, given as severity by kind."""
    irradiance_scale = 1.0
    if FaultKind.PARTIAL_SHADING in severities:
        irradiance_scale *= 1.0 - severities[FaultKind.PARTIAL_SHADING]
    if FaultKind.SOILING in severities:
        irradiance_scale *= 1.0 - severities[FaultKind.SOILING]
    if FaultKind.SERIES_RESISTANCE_RISE in severities:
        rise = severities[FaultKind.SERIES_RESISTANCE_RISE]
        parameters = replace(
            parameters, series_resistance_ohm=parameters.series_resistance_ohm * (1.0 + rise)
        )
    if FaultKind.DIODE_FAILURE in severities:
        ns = datasheet.ns
        remaining = ns - round(severities[FaultKind.DIODE_FAILURE] * ns)
        datasheet = replace(datasheet, ns=remaining, voc_v=datasheet.voc_v * remaining / ns)
    sensor_bias = severities.get(FaultKind.SENSOR_DRIFT, 0.0)
    return PlantEffect(datasheet, parameters, irradiance_scale, sensor_bias)


def _severity_is_valid(kind: FaultKind, severity: float) -> bool:
    if kind in (FaultKind.PARTIAL_SHADING, FaultKind.SOILING):
        return 0.0 <= severity <= 1.0
    if kind is FaultKind.DIODE_FAILURE:
        return 0.0 <= severity < 1.0  # all cells bypassed would leave no module
    if kind is FaultKind.SERIES_RESISTANCE_RISE:
        return severity >= 0.0
    return severity > -1.0  # sensor drift
