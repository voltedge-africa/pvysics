import pytest

from pvysics.gui.metric_strip import GAUGE_SCALE_FACTOR, MetricStrip, split_reading
from pvysics.gui.palette import DARK, LIGHT
from pvysics.run import State

GROUPS = [("Plant", [("G", "Irradiance G"), ("V", "Voltage V")]), ("Comparison", [("dev", "Deviation")])]


@pytest.mark.parametrize(
    ("text", "expected"),
    [("57 W/m²", ("57", "W/m²")), ("24.4 °C", ("24.4", "°C")), ("-32.2 %", ("-32.2", "%")), ("-", ("-", ""))],
)
def test_a_reading_splits_into_its_number_and_its_unit(text, expected):
    assert split_reading(text) == expected


def test_the_strip_loads_its_qml_and_starts_with_placeholders(qtbot):
    strip = MetricStrip(GROUPS, LIGHT, gauge_key="dev")
    qtbot.addWidget(strip)

    assert strip.value("G") == "-"
    assert strip.height() > 0


def test_values_are_written_and_read_back_by_key_and_clear_resets_them(qtbot):
    strip = MetricStrip(GROUPS, LIGHT)
    qtbot.addWidget(strip)

    strip.set_values({"G": "845 W/m²", "V": "26.1 V"})

    assert (strip.value("G"), strip.value("V")) == ("845 W/m²", "26.1 V")
    strip.clear()
    assert strip.value("G") == "-"


def test_a_figure_can_sit_on_a_coloured_pill(qtbot):
    strip = MetricStrip(GROUPS, LIGHT)
    qtbot.addWidget(strip)

    strip.set_value("G", "Abnormal", fill="#c62828", text_colour="#ffffff")

    assert strip.fill("G") == "#c62828"
    strip.set_value("G", "5 W")
    assert strip.fill("G") is None


def test_the_gauge_follows_the_deviation_state_and_limits(qtbot):
    strip = MetricStrip(GROUPS, LIGHT, gauge_key="dev")
    qtbot.addWidget(strip)

    strip.set_limits(5.0, 10.0)
    assert strip.gauge_reading is None
    assert strip.gauge_scale_pct == pytest.approx(GAUGE_SCALE_FACTOR * 10.0)
    strip.set_gauge(-12.0, State.ABNORMAL, 5.0, 10.0)
    assert strip.gauge_reading == pytest.approx(12.0)
    assert strip.gauge_state is State.ABNORMAL
    strip.clear()
    assert strip.gauge_reading is None


def test_the_strip_follows_a_palette_change(qtbot):
    strip = MetricStrip(GROUPS, LIGHT)
    qtbot.addWidget(strip)

    strip.set_palette(DARK)

    assert strip.colours["text"] == DARK.text
