import pytest

from pvysics.gui.metric_tile import MetricSet, MetricTile, split_reading


@pytest.mark.parametrize(
    ("text", "expected"),
    [("57 W/m²", ("57", "W/m²")), ("24.4 °C", ("24.4", "°C")), ("-32.2 %", ("-32.2", "%")), ("-", ("-", ""))],
)
def test_a_reading_splits_into_its_number_and_its_unit(text, expected):
    assert split_reading(text) == expected


def test_a_tile_shows_the_number_and_the_unit_and_reads_back_the_whole_reading(qtbot):
    tile = MetricTile("Irradiance G")
    qtbot.addWidget(tile)

    assert tile.text() == "-"
    tile.set_text("845 W/m²")
    assert tile.text() == "845 W/m²"
    tile.clear()
    assert tile.text() == "-"


def test_a_tile_can_hold_a_widget_beside_its_figure(qtbot):
    from PyQt6.QtWidgets import QLabel

    side = QLabel("gauge")
    tile = MetricTile("Deviation", side=side)
    qtbot.addWidget(tile)

    assert tile.isAncestorOf(side)


def test_a_metric_set_reads_and_writes_its_tiles_by_key(qtbot):
    tiles = {"G": MetricTile("Irradiance G"), "V": MetricTile("Voltage V")}
    for tile in tiles.values():
        qtbot.addWidget(tile)
    metrics = MetricSet(tiles)

    metrics.set_values({"G": "10 W/m²", "V": "26.1 V"})

    assert (metrics.value("G"), metrics.value("V")) == ("10 W/m²", "26.1 V")
    metrics.clear()
    assert metrics.value("G") == "-"
