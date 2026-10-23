from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from pvysics.gui import model_view
from pvysics.gui.data_bus import DataBus
from pvysics.gui.main_window import MainWindow
from pvysics.gui.model_view import CircuitWidget, EquationsWidget, ModelView
from pvysics.gui.playback import SPEEDS, PlaybackController
from pvysics.gui.process_view import PLACEHOLDER, format_number
from pvysics.profile import Profile
from pvysics.run import RunConfig, SensorModel, bundled_run_config
from pvysics.single_diode import fit_parameters, solve_curve

FASTEST = SPEEDS[-1]
NOISE_FREE = SensorModel(
    irradiance_noise_pct=0.0,
    temperature_noise_c=0.0,
    voltage_noise_v=0.0,
    current_noise_a=0.0,
    voltage_step_v=0.0,
    current_step_a=0.0,
)


def midday_config(sensors: SensorModel | None = None) -> RunConfig:
    """The bundled day cut to 10:00 to 14:00, one Sample a minute."""
    config = bundled_run_config(seed=1)
    profile = config.profile
    cut = Profile(
        timestamps=profile.timestamps[10:15],
        irradiance=profile.irradiance[10:15],
        temperature=profile.temperature[10:15],
    )
    config = replace(config, profile=cut)
    return config if sensors is None else replace(config, sensors=sensors)


class Harness:
    """A ModelView on its own PlaybackController and DataBus, shown and sized like a window."""

    def __init__(self, qtbot, config: RunConfig | None = None) -> None:
        self.bus = DataBus()
        self.config = bundled_run_config(seed=1) if config is None else config
        self.controller = PlaybackController(self.config, self.bus)
        self.controller.set_speed(FASTEST)
        self.samples = []
        self.bus.sample.connect(self.samples.append)
        self.view = ModelView(self.controller, self.bus)
        qtbot.addWidget(self.view)
        self.view.resize(1280, 960)
        self.view.show()
        qtbot.waitExposed(self.view)

    def play_one_tick(self) -> None:
        self.controller.tick()
        self.view.refresh()


@pytest.fixture
def make_harness(qtbot):
    """Builds harnesses for a test and pauses their playback at teardown, before objects go."""
    harnesses = []

    def make(config: RunConfig | None = None) -> "Harness":
        harness = Harness(qtbot, config)
        harnesses.append(harness)
        return harness

    yield make
    for harness in harnesses:
        harness.controller.pause()


def test_design_assets_are_packaged_copies_of_the_documentation_assets(qtbot):
    package_assets = files("pvysics") / "gui" / "assets"
    repo = Path(__file__).resolve().parents[1]
    sources = {
        "circuit_sdm.svg": repo / "documentation/wireframes/svg/circuit_sdm.svg",
        "eq_sdm.png": repo / "documentation/presentation/png/eq_sdm.png",
        "eq_iph.png": repo / "documentation/presentation/png/eq_iph.png",
        "eq_vt.png": repo / "documentation/presentation/png/eq_vt.png",
    }
    for name, source in sources.items():
        if source.exists():  # the PNG folder is git-ignored, so a clone may not have it
            assert (package_assets / name).read_bytes() == source.read_bytes()
    EquationsWidget()  # loads all three equation images, or raises
    assert CircuitWidget().aspect == pytest.approx(435.097507874 / 133.017001969)


def test_parameters_shown_are_the_fit_the_twin_predicts_with(make_harness):
    harness = make_harness()
    datasheet = harness.config.datasheet
    fit = fit_parameters(datasheet)

    assert harness.view.parameters == fit
    assert harness.view.parameter_panel.value("rs") == f"{format_number(fit.series_resistance_ohm, 3)} Ω"
    assert harness.view.parameter_panel.value("ns") == str(datasheet.ns)
    assert harness.view.datasheet_panel.value("vmpp") == f"{format_number(datasheet.vmpp_v, 2)} V"

    harness.controller.start()
    harness.play_one_tick()
    sample = harness.samples[-1]
    shown_model = solve_curve(datasheet, sample.measured_irradiance, sample.measured_temperature, harness.view.parameters)
    assert shown_model.mpp_power == pytest.approx(sample.power_predicted)


def test_curve_is_for_the_measured_gt_and_follows_the_run(make_harness):
    harness = make_harness(config=midday_config())
    harness.controller.start()
    keys_seen = set()
    while not harness.controller.is_finished:
        harness.play_one_tick()
        if harness.samples:
            sample = harness.samples[-1]
            assert harness.view.curve_key == (sample.measured_irradiance, sample.measured_temperature)
            assert harness.view.curve.mpp_power == pytest.approx(sample.power_predicted)
            keys_seen.add(harness.view.curve_key)
    assert len(keys_seen) > 1  # the curve moved as G and T changed over the day


def test_measured_operating_point_is_drawn_at_the_measured_v_and_i(make_harness):
    harness = make_harness(config=midday_config())
    harness.controller.start()
    for _ in range(8):
        harness.play_one_tick()
    sample = harness.samples[-1]

    assert harness.view.operating_point == (sample.measured_voltage, sample.measured_current)


def test_healthy_plant_operating_point_sits_at_or_below_the_twin_mpp(make_harness):
    harness = make_harness(config=midday_config(sensors=NOISE_FREE))
    harness.controller.start()
    checked = 0
    while not harness.controller.is_finished:
        harness.play_one_tick()
        for sample in harness.samples[checked:]:
            if sample.power_predicted >= 5.0:  # daylight only
                measured = sample.measured_voltage * sample.measured_current
                assert measured <= sample.power_predicted * (1.0 + 1e-9)
        checked = len(harness.samples)
    assert checked > 0


def test_curve_is_not_recomputed_while_gt_have_not_changed(make_harness, monkeypatch):
    calls = []
    real = model_view.solve_curve

    def counting(*args, **kwargs):
        calls.append(args[1:3])
        return real(*args, **kwargs)

    monkeypatch.setattr(model_view, "solve_curve", counting)
    harness = make_harness(config=midday_config(sensors=NOISE_FREE))
    harness.controller.start()
    harness.controller.tick()
    harness.view.refresh()
    harness.view.refresh()
    assert len(calls) == 1

    harness.bus.sample.emit(harness.samples[-1])  # same G and T again
    harness.view.refresh()
    assert len(calls) == 1


def test_reset_clears_the_curve_and_the_readings(make_harness):
    harness = make_harness(config=midday_config())
    harness.controller.start()
    harness.play_one_tick()
    assert harness.view.curve is not None

    harness.controller.reset()

    assert harness.view.curve is None
    assert harness.view.operating_point is None
    assert harness.view.live_panel.value("G") == PLACEHOLDER
    assert harness.view.output_panel.value("p_mpp") == PLACEHOLDER


def test_offscreen_smoke_opens_the_model_view_during_a_run(make_harness):
    harness = make_harness()
    harness.controller.start()
    for _ in range(5):
        harness.play_one_tick()
    harness.view.grab()

    assert harness.view.curve is not None
    assert harness.view.live_panel.value("G") != PLACEHOLDER
    assert harness.view.output_panel.value("deviation").endswith(" %")


@pytest.mark.parametrize("size", [(640, 480), (1280, 960), (1920, 1080)])
def test_schematic_and_equations_keep_their_aspect_ratio_at_common_sizes(make_harness, size):
    harness = make_harness()
    harness.view.resize(*size)
    QApplication.processEvents()
    circuit = harness.view.circuit
    drawn = circuit.drawn_rect()

    assert drawn.width() / drawn.height() == pytest.approx(circuit.aspect)
    assert QRectF(circuit.rect()).contains(drawn)
    natural = []
    for name in model_view.EQUATION_IMAGES:
        pixmap = QPixmap()
        assert pixmap.loadFromData((files("pvysics") / "gui" / "assets" / name).read_bytes())
        natural.append(pixmap.width() / pixmap.height())
    for picture, aspect in zip(harness.view.equations.picture_rects(), natural):
        assert QRectF(harness.view.equations.rect()).contains(picture)
        assert picture.width() / picture.height() == pytest.approx(aspect)


def test_the_view_paints_at_a_high_dpi_scale(make_harness):
    harness = make_harness(config=midday_config())
    harness.controller.start()
    harness.play_one_tick()
    image = QImage(harness.view.size() * 2, QImage.Format.Format_ARGB32)
    image.setDevicePixelRatio(2.0)
    painter = QPainter(image)
    harness.view.render(painter)
    painter.end()

    assert not image.isNull()
    assert image.devicePixelRatio() == 2.0


def test_main_window_has_process_and_model_tabs_and_the_model_tab_follows_the_run(qtbot):
    window = MainWindow(config=midday_config())
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    tabs = window.centralWidget()
    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Process", "Model", "Setup"]

    tabs.setCurrentWidget(window.model_view)
    window.playback.set_speed(SPEEDS[-1])
    window.process_view.start_button.click()
    for _ in range(5):
        window.playback.tick()
        window.model_view.refresh()

    assert window.model_view.curve is not None
    assert window.model_view.live_panel.value("G") != PLACEHOLDER
    window.playback.pause()
