from dataclasses import replace

import pytest

from pvysics.faults import FaultKind, default_fault
from pvysics.gui.data_bus import DataBus
from pvysics.gui.playback import SPEEDS, TICKS_PER_SECOND, PlaybackController
from pvysics.profile import Profile
from pvysics.run import RunConfig, Simulation, Thresholds, bundled_run_config

FASTEST = SPEEDS[-1]


def short_config(samples: int) -> RunConfig:
    """The bundled day cut to its first `samples` hours, one Sample per hour."""
    profile = bundled_run_config().profile
    cut = Profile(
        timestamps=profile.timestamps[:samples],
        irradiance=profile.irradiance[:samples],
        temperature=profile.temperature[:samples],
    )
    return replace(bundled_run_config(), profile=cut, time_step_s=3600.0)


class Recorder:
    """Collects everything a window would see on the bus."""

    def __init__(self, bus: DataBus) -> None:
        self.samples = []
        self.events = []
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
    controller = PlaybackController(bundled_run_config(), bus)

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
    config = bundled_run_config(seed=0)
    controller = PlaybackController(config, bus)
    controller.set_speed(FASTEST)
    controller.start()
    for _ in range(10):
        controller.tick()

    controller.reset()
    recorder.samples.clear()
    controller.start()
    controller.tick()

    assert recorder.resets == 1
    assert recorder.samples[0] == Simulation(config).step()


def test_reset_stops_a_running_run(bus):
    controller = PlaybackController(bundled_run_config(), bus)
    controller.start()

    controller.reset()

    assert not controller.is_running


def test_reset_also_removes_injected_faults(bus):
    recorder = Recorder(bus)
    controller = PlaybackController(bundled_run_config(), bus)
    controller.set_speed(FASTEST)
    controller.inject(default_fault(FaultKind.SOILING))
    controller.reset()

    controller.start()
    controller.tick()

    assert all(sample.active_faults == () for sample in recorder.samples)


def test_speed_change_while_running_does_not_restart_the_run(bus):
    recorder = Recorder(bus)
    controller = PlaybackController(bundled_run_config(), bus)
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
    controller = PlaybackController(bundled_run_config(), bus)
    controller.set_speed(60.0)  # one simulated minute per second: one sample every 30 ticks
    controller.start()

    controller.tick()
    assert len(recorder.samples) == 1
    for _ in range(TICKS_PER_SECOND - 1):
        controller.tick()
    assert len(recorder.samples) == 2


def test_fastest_speed_plays_a_whole_day_in_a_few_seconds_without_flooding_a_tick(bus):
    recorder = Recorder(bus)
    config = bundled_run_config()
    controller = PlaybackController(config, bus)
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
    assert len(recorder.samples) == Simulation(config).length
    assert ticks <= 100  # about 3 seconds at 30 ticks per second
    assert max(emitted_per_tick) <= 20


def test_start_is_ignored_once_the_run_has_finished(bus):
    controller = PlaybackController(short_config(1), bus)
    controller.set_speed(FASTEST)
    controller.start()
    controller.tick()

    assert controller.is_finished
    assert not controller.is_running
    controller.start()
    assert not controller.is_running


def test_running_changed_is_emitted_on_start_pause_and_finish(bus):
    controller = PlaybackController(short_config(1), bus)
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
    config = short_config(3)  # samples at 00:00, 01:00 and 02:00
    controller = PlaybackController(config, bus)
    controller.set_speed(1800.0)  # 60 simulated seconds per tick: 60 ticks per hour
    controller.inject(default_fault(FaultKind.PARTIAL_SHADING))  # applies from the first sample
    controller.start()

    controller.tick()
    assert [sample.timestamp for sample in recorder.samples] == [config.profile.timestamps[0]]
    assert [event.detail for event in recorder.events] == ["none -> partial shading"]

    for _ in range(59):
        controller.tick()
    assert len(recorder.samples) == 2
    assert len(recorder.events) == 1


def test_the_bus_is_one_object_that_every_subscriber_receives_from(bus):
    first = Recorder(bus)
    second = Recorder(bus)
    controller = PlaybackController(short_config(2), bus)
    controller.set_speed(3600.0 * TICKS_PER_SECOND)  # one simulated hour per tick
    controller.start()

    controller.tick()

    assert first.samples == second.samples
    assert len(first.samples) == 2


def test_speed_must_be_positive(bus):
    controller = PlaybackController(bundled_run_config(), bus)

    with pytest.raises(ValueError):
        controller.set_speed(0.0)


def test_load_replaces_the_run_and_starts_it_from_the_beginning(bus):
    recorder = Recorder(bus)
    controller = PlaybackController(bundled_run_config(), bus)
    controller.set_speed(FASTEST)
    controller.start()
    controller.tick()
    new_config = replace(bundled_run_config(seed=7), profile=short_config(2).profile)

    controller.load(new_config)
    recorder.samples.clear()
    controller.start()
    controller.tick()

    assert controller.config is new_config
    assert recorder.resets == 1
    assert recorder.samples[0] == Simulation(new_config).step()


def test_load_with_an_invalid_config_keeps_the_current_run(bus):
    recorder = Recorder(bus)
    config = bundled_run_config()
    controller = PlaybackController(config, bus)
    bad = replace(config, thresholds=Thresholds(warning_pct=10.0, abnormal_pct=5.0))

    with pytest.raises(ValueError):
        controller.load(bad)

    assert controller.config is config
    assert recorder.resets == 0
