import numpy as np
import pytest

from pvysics.gui.data_bus import DataBus
from pvysics.gui.main_window import bundled_result
from pvysics.gui.playback import SPEEDS, TICKS_PER_SECOND, PlaybackController
from pvysics.run import Event, RunResult, Sample, State, bundled_run_config

ORIGIN = np.datetime64("2025-01-15T06:00:00")
FASTEST = SPEEDS[-1]


def sample_at(offset_s: float, state: State = State.NORMAL, deviation: float = 0.0) -> Sample:
    return Sample(
        timestamp=ORIGIN + np.timedelta64(round(offset_s), "s"),
        true_irradiance=500.0,
        true_temperature=25.0,
        measured_irradiance=500.0,
        measured_temperature=25.0,
        measured_voltage=30.0,
        measured_current=5.0,
        power_measured=150.0,
        power_predicted=150.0,
        deviation_pct=deviation,
        state=state,
    )


def hand_made_run(samples: list[Sample], events: list[Event] | None = None) -> RunResult:
    return RunResult(config=bundled_run_config(), samples=samples, events=events or [])


class Recorder:
    """Collects everything a window would see on the bus."""

    def __init__(self, bus: DataBus) -> None:
        self.samples: list[Sample] = []
        self.events: list[Event] = []
        self.resets = 0
        bus.sample.connect(self.samples.append)
        bus.event.connect(self.events.append)
        bus.run_reset.connect(self._count_reset)

    def _count_reset(self) -> None:
        self.resets += 1


@pytest.fixture
def bus(qtbot) -> DataBus:
    return DataBus()


def test_start_plays_the_run_and_pause_freezes_it(bus):
    recorder = Recorder(bus)
    controller = PlaybackController(bundled_result(), bus)

    controller.start()
    controller.tick()
    played = len(recorder.samples)
    controller.pause()
    controller.tick()
    controller.tick()

    assert played > 0
    assert not controller.is_running
    assert len(recorder.samples) == played


def test_reset_returns_the_run_to_its_start(bus):
    recorder = Recorder(bus)
    result = bundled_result()
    controller = PlaybackController(result, bus)
    controller.set_speed(FASTEST)
    controller.start()
    for _ in range(10):
        controller.tick()

    controller.reset()
    recorder.samples.clear()
    controller.start()
    controller.tick()

    assert recorder.resets == 1
    assert recorder.samples[0] == result.samples[0]


def test_reset_stops_a_running_run(bus):
    controller = PlaybackController(bundled_result(), bus)
    controller.start()

    controller.reset()

    assert not controller.is_running


def test_speed_change_while_running_does_not_restart_the_run(bus):
    recorder = Recorder(bus)
    controller = PlaybackController(bundled_result(), bus)
    controller.start()
    controller.tick()
    before = len(recorder.samples)

    controller.set_speed(FASTEST)
    controller.tick()

    assert controller.is_running
    assert controller.speed == FASTEST
    assert recorder.resets == 0
    assert len(recorder.samples) > before
    timestamps = [sample.timestamp for sample in recorder.samples]
    assert timestamps == sorted(set(timestamps))


def test_speed_sets_how_fast_the_run_advances(bus):
    recorder = Recorder(bus)
    controller = PlaybackController(bundled_result(), bus)
    controller.set_speed(60.0)  # one simulated minute per second: one sample every 30 ticks
    controller.start()

    controller.tick()
    assert len(recorder.samples) == 1
    for _ in range(TICKS_PER_SECOND - 1):
        controller.tick()
    assert len(recorder.samples) == 2


def test_fastest_speed_plays_a_whole_day_in_a_few_seconds_without_flooding_a_tick(bus):
    recorder = Recorder(bus)
    controller = PlaybackController(bundled_result(), bus)
    controller.set_speed(FASTEST)
    controller.start()

    ticks = 0
    emitted_per_tick = []
    while controller.is_running and ticks < 1000:
        before = len(recorder.samples)
        controller.tick()
        emitted_per_tick.append(len(recorder.samples) - before)
        ticks += 1

    assert controller.is_finished
    assert len(recorder.samples) == len(bundled_result().samples)
    assert ticks <= 100  # about 3 seconds at 30 ticks per second
    assert max(emitted_per_tick) <= 20


def test_start_is_ignored_once_the_run_has_finished(bus):
    controller = PlaybackController(hand_made_run([sample_at(0)]), bus)
    controller.set_speed(FASTEST)
    controller.start()
    controller.tick()

    assert controller.is_finished
    assert not controller.is_running
    controller.start()
    assert not controller.is_running


def test_running_changed_is_emitted_on_start_pause_and_finish(bus):
    controller = PlaybackController(hand_made_run([sample_at(0)]), bus)
    changes = []
    controller.running_changed.connect(changes.append)

    controller.start()
    controller.pause()
    controller.start()
    controller.set_speed(FASTEST)
    controller.tick()

    assert changes == [True, False, True, False]


def test_each_sample_and_event_is_emitted_once_when_the_clock_reaches_it(bus):
    recorder = Recorder(bus)
    state_change = Event(ORIGIN + np.timedelta64(60, "s"), "state", "Normal -> Warning")
    run_result = hand_made_run(
        [sample_at(0), sample_at(60, State.WARNING, -6.0), sample_at(120)],
        events=[state_change],
    )
    controller = PlaybackController(run_result, bus)
    controller.set_speed(1800.0)  # 60 simulated seconds per tick
    controller.start()

    controller.tick()
    assert [sample.timestamp for sample in recorder.samples] == [
        run_result.samples[0].timestamp,
        run_result.samples[1].timestamp,
    ]
    assert recorder.events == [state_change]

    controller.tick()
    assert len(recorder.samples) == 3
    assert recorder.events == [state_change]


def test_the_bus_is_one_object_that_every_subscriber_receives_from(bus):
    first = Recorder(bus)
    second = Recorder(bus)
    controller = PlaybackController(hand_made_run([sample_at(0), sample_at(60)]), bus)
    controller.set_speed(FASTEST)
    controller.start()

    controller.tick()

    assert first.samples == second.samples
    assert len(first.samples) == 2


def test_speed_must_be_positive(bus):
    controller = PlaybackController(bundled_result(), bus)

    with pytest.raises(ValueError):
        controller.set_speed(0.0)


def test_a_run_without_samples_is_rejected(bus):
    with pytest.raises(ValueError):
        PlaybackController(hand_made_run([]), bus)
