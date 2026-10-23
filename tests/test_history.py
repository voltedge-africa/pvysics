import numpy as np

from pvysics.history import RunHistory
from pvysics.run import Event, Sample, State


def sample_at(hour: float, power_w: float) -> Sample:
    stamp = np.datetime64("2025-01-15T00:00:00") + np.timedelta64(round(hour * 3600), "s")
    return Sample(
        timestamp=stamp,
        true_irradiance=800.0,
        true_temperature=25.0,
        measured_irradiance=800.0,
        measured_temperature=25.0,
        measured_voltage=30.0,
        measured_current=power_w / 30.0,
        power_measured=power_w,
        power_predicted=power_w,
        deviation_pct=0.0,
        state=State.NORMAL,
    )


def test_history_keeps_every_sample_and_event_in_time_order():
    history = RunHistory()
    first, second = sample_at(0.0, 100.0), sample_at(1.0, 200.0)
    event = Event(second.timestamp, "state", "Normal -> Warning")

    history.record_sample(first)
    history.record_sample(second)
    history.record_event(event)

    assert history.sample_count == 2
    assert history.samples_from(0) == [first, second]
    assert history.samples_from(1) == [second]
    assert history.events_from(0) == [event]
    assert history.latest is second
    assert history.origin == first.timestamp


def test_energy_is_the_trapezoid_integral_of_measured_power_in_watt_hours():
    history = RunHistory()
    assert history.energy_wh == 0.0

    history.record_sample(sample_at(0.0, 100.0))
    assert history.energy_wh == 0.0  # one sample spans no time yet

    history.record_sample(sample_at(1.0, 300.0))  # 100 W to 300 W over one hour
    assert history.energy_wh == 200.0

    history.record_sample(sample_at(1.5, 300.0))  # 300 W held for half an hour
    assert history.energy_wh == 350.0


def test_clear_empties_the_history_and_restarts_the_energy():
    history = RunHistory()
    history.record_sample(sample_at(0.0, 100.0))
    history.record_sample(sample_at(1.0, 100.0))
    history.record_event(Event(sample_at(0.0, 0.0).timestamp, "fault", "none -> soiling"))

    history.clear()

    assert history.sample_count == 0
    assert history.event_count == 0
    assert history.latest is None
    assert history.origin is None
    assert history.energy_wh == 0.0
