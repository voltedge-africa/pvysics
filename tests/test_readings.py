import numpy as np

from pvysics.gui.process_view import format_readings
from pvysics.run import Sample, State


def sample_with(power_w: float, deviation_pct: float = 0.0) -> Sample:
    """A night-time Sample: the plant and the twin both read just below zero after rounding."""
    stamp = np.datetime64("2025-01-15T03:00:00", "s")
    return Sample(
        timestamp=stamp,
        true_irradiance=0.0,
        true_temperature=10.0,
        measured_irradiance=0.0,
        measured_temperature=10.0,
        measured_voltage=0.0,
        measured_current=-0.02,
        power_measured=power_w,
        power_predicted=power_w,
        deviation_pct=deviation_pct,
        state=State.NORMAL,
    )


def test_negative_zero_power_reads_as_zero_not_minus_zero():
    readings = format_readings(sample_with(power_w=-0.04))

    assert readings["P"] == "0.0 W"
    assert readings["P_pred"] == "0.0 W"


def test_negative_zero_current_and_voltage_read_as_zero():
    readings = format_readings(sample_with(power_w=0.0))

    assert readings["I"] == "0.0 A"
    assert readings["V"] == "0.0 V"


def test_real_negative_values_keep_their_sign():
    readings = format_readings(sample_with(power_w=-3.0))

    assert readings["P"] == "-3.0 W"
