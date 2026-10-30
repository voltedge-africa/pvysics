"""Live readings: parsing, scoring in arrival order, and the rule that a late start raises nothing. Headless."""

import numpy as np
import pytest

from pvysics.dataset import score_row
from pvysics.live import LiveScorer, ReadingError, parse_reading
from pvysics.run import State, bundled_run_config
from pvysics.single_diode import solve_curve

CONFIG = bundled_run_config(seed=0)


def healthy(stamp: str, g: float = 800.0, t: float = 35.0, drop: float = 1.0) -> dict:
    """A reading from a healthy module held at its maximum power point; drop scales the current."""
    curve = solve_curve(CONFIG.datasheet, g, t)
    return {"timestamp": stamp, "g": g, "t": t, "v": curve.mpp_voltage, "i": curve.mpp_current * drop}


# parse


def test_a_reading_is_read_from_short_or_long_keys_in_any_case():
    short = parse_reading({"timestamp": "2025-01-15T10:00:00", "G": 640, "t": 32.5, "v": 29.0, "I": 5.2})
    long = parse_reading(
        {"Timestamp": "2025-01-15T10:00:00", "irradiance_w_m2": 640, "temperature_c": 32.5, "voltage_v": 29.0, "current_a": 5.2}
    )

    assert short == long
    assert short.power == pytest.approx(29.0 * 5.2)
    assert short.timestamp == np.datetime64("2025-01-15T10:00:00", "s")


def test_a_reading_without_a_time_gets_the_time_it_arrived():
    arrived = np.datetime64("2025-01-15T13:30:05", "s")

    reading = parse_reading({"g": 640, "t": 32.5, "v": 29.0, "i": 5.2}, received_at=arrived)

    assert reading.timestamp == arrived


def test_a_reading_with_only_power_is_accepted():
    reading = parse_reading({"g": 640, "t": 32.5, "power": 150.0}, received_at=np.datetime64("2025-01-15T10:00:00", "s"))

    assert reading.power == 150.0
    assert reading.voltage == 0.0  # no voltage: the twin predicts the maximum power


@pytest.mark.parametrize(
    "payload, words",
    [
        ({"t": 30, "v": 29, "i": 5}, "irradiance"),
        ({"g": 600, "v": 29, "i": 5}, "temperature"),
        ({"g": 600, "t": 30, "v": 29}, "power, or both"),
        ({"g": 600, "t": 30}, "power, or both"),
        ({"g": -5, "t": 30, "v": 29, "i": 5}, "negative"),
        ({"g": "bright", "t": 30, "v": 29, "i": 5}, "not a number"),
        ({"g": float("nan"), "t": 30, "v": 29, "i": 5}, "finite"),
        ({"g": 600, "t": 30, "v": 29, "i": 5, "timestamp": "yesterday"}, "not a date"),
        ([1, 2, 3], "JSON object"),
        ({"g": True, "t": 30, "v": 29, "i": 5}, "not a number"),
    ],
)
def test_a_bad_reading_is_refused_with_the_reason(payload, words):
    with pytest.raises(ReadingError, match=words):
        parse_reading(payload, received_at=np.datetime64("2025-01-15T10:00:00", "s"))


# scoring


def test_a_live_reading_scores_exactly_as_the_same_dataset_row():
    reading = parse_reading(healthy("2025-01-15T10:00:00", drop=0.8))
    scorer = LiveScorer(CONFIG)

    sample, events = scorer.score(reading)

    expected, _ = score_row(CONFIG, reading.timestamp, reading.irradiance, reading.temperature,
                            reading.voltage, reading.current, reading.power)
    assert sample == expected
    assert events == []  # the first reading has no state to change from


def test_starting_to_send_at_midday_raises_nothing():
    """No readings came in the morning; the first one at 13:00 is simply scored, and is Normal."""
    scorer = LiveScorer(CONFIG)

    sample, events = scorer.score(parse_reading(healthy("2025-01-15T13:00:00")))

    assert sample.state is State.NORMAL
    assert events == []
    assert scorer.accepted == 1


def test_a_gap_between_readings_raises_nothing():
    scorer = LiveScorer(CONFIG)
    scorer.score(parse_reading(healthy("2025-01-15T10:00:00")))

    sample, events = scorer.score(parse_reading(healthy("2025-01-15T15:40:00")))  # nothing for five and a half hours

    assert sample.state is State.NORMAL
    assert events == []


def test_a_change_of_state_is_reported_as_an_event():
    scorer = LiveScorer(CONFIG)
    scorer.score(parse_reading(healthy("2025-01-15T10:00:00")))

    sample, events = scorer.score(parse_reading(healthy("2025-01-15T10:01:00", drop=0.7)))  # 30 % less current

    assert sample.state is State.ABNORMAL
    assert [(e.kind, e.detail) for e in events] == [("state", "Normal -> Abnormal")]
    assert events[0].timestamp == sample.timestamp


def test_a_reading_that_does_not_come_after_the_last_is_refused():
    scorer = LiveScorer(CONFIG)
    scorer.score(parse_reading(healthy("2025-01-15T10:00:00")))

    for stamp in ("2025-01-15T10:00:00", "2025-01-15T09:59:00"):
        with pytest.raises(ReadingError, match="time does not increase"):
            scorer.score(parse_reading(healthy(stamp)))

    assert scorer.accepted == 1  # the refused ones changed nothing
    scorer.score(parse_reading(healthy("2025-01-15T10:01:00")))
    assert scorer.accepted == 2


# the log


def test_the_live_log_imports_as_a_dataset_and_scores_like_the_live_run(tmp_path):
    from pvysics.dataset import analyse_dataset, read_measurement_file
    from pvysics.live import LiveLog

    log = LiveLog(tmp_path)
    scorer = LiveScorer(CONFIG)
    live_samples = []
    for minute, drop in enumerate((1.0, 1.0, 0.7)):
        reading = parse_reading(healthy(f"2025-01-15T10:0{minute}:00", drop=drop))
        live_samples.append(scorer.score(reading)[0])
        log.append(reading)
    log.close()

    report = analyse_dataset(read_measurement_file(log.path), CONFIG)

    assert [s.state for s in report.samples] == [s.state for s in live_samples]
    assert report.samples[2].deviation_pct == pytest.approx(live_samples[2].deviation_pct, rel=1e-6)
    assert log.path.parent == tmp_path and log.path.name.startswith("live-")
