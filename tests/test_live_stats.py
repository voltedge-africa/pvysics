import numpy as np
import pytest

from pvysics.live_stats import DeviationHistogram, StateTimes
from pvysics.run import Sample, State


def sample(seconds: float, state: State = State.NORMAL, deviation_pct: float = 0.0, predicted_w: float = 200.0) -> Sample:
    """A Sample at `seconds` after a fixed start, with the given State, deviation and predicted power."""
    stamp = np.datetime64("2025-01-15T06:00:00") + np.timedelta64(round(seconds), "s")
    return Sample(
        timestamp=stamp,
        true_irradiance=800.0,
        true_temperature=25.0,
        measured_irradiance=800.0,
        measured_temperature=25.0,
        measured_voltage=30.0,
        measured_current=5.0,
        power_measured=predicted_w * (1.0 + deviation_pct / 100.0),
        power_predicted=predicted_w,
        deviation_pct=deviation_pct,
        state=state,
    )


# Histogram

def test_histogram_bins_cover_minus_ten_to_plus_ten_percent_in_half_percent_steps():
    histogram = DeviationHistogram()

    assert histogram.edges[0] == pytest.approx(-10.0)
    assert histogram.edges[-1] == pytest.approx(10.0)
    assert histogram.bin_width_pct == pytest.approx(0.5)
    assert len(histogram.counts) == 40
    assert histogram.centres[0] == pytest.approx(-9.75)


def test_histogram_counts_each_daylight_sample_in_the_bin_that_holds_its_deviation():
    histogram = DeviationHistogram()
    histogram.add([sample(0, deviation_pct=0.2), sample(60, deviation_pct=0.3), sample(120, deviation_pct=-4.1)])

    bin_of = lambda value: int(np.searchsorted(histogram.edges, value, side="right") - 1)
    assert histogram.total == 3
    assert histogram.counts[bin_of(0.2)] == 2  # 0.2 and 0.3 share the 0 to 0.5 bin
    assert histogram.counts[bin_of(-4.1)] == 1
    assert histogram.counts.sum() == 3


def test_histogram_leaves_night_samples_out_because_their_deviation_is_only_a_placeholder():
    histogram = DeviationHistogram()
    histogram.add([sample(0, deviation_pct=0.0, predicted_w=0.0), sample(60, deviation_pct=3.0, predicted_w=200.0)])

    assert histogram.total == 1
    assert histogram.counts.sum() == 1


def test_histogram_keeps_deviations_outside_the_range_apart_from_the_bins():
    histogram = DeviationHistogram()
    histogram.add([sample(0, deviation_pct=-35.0), sample(60, deviation_pct=12.0), sample(120, deviation_pct=1.0)])

    assert histogram.below_range == 1
    assert histogram.above_range == 1
    assert histogram.total == 1


def test_histogram_adds_only_the_samples_it_is_given_so_counts_accumulate_across_ticks():
    histogram = DeviationHistogram()
    histogram.add([sample(0, deviation_pct=1.0)])
    histogram.add([sample(60, deviation_pct=1.0), sample(120, deviation_pct=-1.0)])

    assert histogram.total == 3
    histogram.clear()
    assert histogram.total == 0
    assert histogram.below_range == 0 and histogram.above_range == 0


# State time

def test_time_in_state_sums_to_the_elapsed_simulated_time():
    samples = [
        sample(0, State.NORMAL),
        sample(60, State.NORMAL),
        sample(180, State.WARNING),
        sample(240, State.ABNORMAL),
        sample(900, State.NORMAL),
    ]
    times = StateTimes()
    times.add(samples)

    elapsed = (samples[-1].timestamp - samples[0].timestamp) / np.timedelta64(1, "s")
    assert times.total_seconds == pytest.approx(elapsed)
    assert times.seconds_in(State.NORMAL) == pytest.approx(60 + 120)  # the gaps after the two Normal samples before 180 s
    assert times.seconds_in(State.WARNING) == pytest.approx(60)
    assert times.seconds_in(State.ABNORMAL) == pytest.approx(660)


def test_night_samples_count_as_normal_time_as_the_engine_reports_them():
    night = [sample(0, State.NORMAL, predicted_w=0.0), sample(3600, State.NORMAL, predicted_w=0.0)]
    times = StateTimes()
    times.add(night)

    assert times.seconds_in(State.NORMAL) == pytest.approx(3600.0)
    assert times.fraction_in(State.NORMAL) == pytest.approx(1.0)


def test_fractions_are_shares_of_the_elapsed_time_and_zero_before_any_time_passes():
    times = StateTimes()
    assert times.fraction_in(State.NORMAL) == 0.0

    times.add([sample(0, State.NORMAL), sample(300, State.ABNORMAL)])
    times.add([sample(600, State.ABNORMAL)])

    assert times.fraction_in(State.NORMAL) == pytest.approx(0.5)
    assert times.fraction_in(State.ABNORMAL) == pytest.approx(0.5)
    assert sum(times.fraction_in(state) for state in State) == pytest.approx(1.0)


def test_incremental_adds_give_the_same_times_as_one_add_and_clear_restarts():
    samples = [sample(60 * index, State.WARNING if index % 3 else State.NORMAL) for index in range(20)]
    whole, parts = StateTimes(), StateTimes()
    whole.add(samples)
    parts.add(samples[:7])
    parts.add(samples[7:])

    for state in State:
        assert parts.seconds_in(state) == pytest.approx(whole.seconds_in(state))

    parts.clear()
    assert parts.total_seconds == 0.0
    parts.add(samples[:2])
    assert parts.total_seconds == pytest.approx(60.0)
