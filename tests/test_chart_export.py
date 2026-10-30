from PyQt6.QtCore import QEvent, QPointF
from PyQt6.QtGui import QEnterEvent

from pvysics.gui.ui_helpers import EXPORT_MARGIN_PX, CompactPlot


def a_plot(qtbot) -> CompactPlot:
    plot = CompactPlot()
    plot.plot([0, 1, 2], [1, 4, 9], name="y")
    plot.resize(400, 300)
    qtbot.addWidget(plot)
    plot.show()
    return plot


def point_into(plot: CompactPlot) -> None:
    where = QPointF(10, 10)
    plot.enterEvent(QEnterEvent(where, where, where))


def test_the_export_button_is_hidden_until_the_pointer_is_over_the_chart(qtbot):
    plot = a_plot(qtbot)

    assert not plot.export_button.isVisible()
    point_into(plot)
    assert plot.export_button.isVisible()
    plot.leaveEvent(QEvent(QEvent.Type.Leave))
    assert not plot.export_button.isVisible()


def test_the_export_button_sits_at_the_top_right_corner_and_follows_a_resize(qtbot):
    plot = a_plot(qtbot)
    point_into(plot)

    button = plot.export_button
    assert button.geometry().top() == EXPORT_MARGIN_PX
    assert button.geometry().right() == plot.width() - EXPORT_MARGIN_PX - 1
    plot.resize(600, 300)
    assert button.geometry().right() == 600 - EXPORT_MARGIN_PX - 1


def test_the_button_offers_the_image_the_data_and_the_way_back_to_the_full_view(qtbot):
    plot = a_plot(qtbot)

    actions = [action.text() for action in plot.export_button.menu().actions() if not action.isSeparator()]

    assert actions == ["Image (PNG)...", "Data (CSV)...", "Reset view"]


def test_the_chart_exports_its_image_and_its_data(qtbot, tmp_path):
    plot = a_plot(qtbot)

    plot.export_image(str(tmp_path / "chart.png"))
    plot.export_data(str(tmp_path / "chart.csv"))

    assert (tmp_path / "chart.png").stat().st_size > 0
    assert (tmp_path / "chart.csv").read_text().splitlines()[0] == "y_x,y_y"


def test_zooming_stops_following_the_data_and_reset_view_restores_it(qtbot):
    plot = a_plot(qtbot)
    plot.setXRange(0, 0.5)

    assert plot.plotItem.vb.state["autoRange"][0] is False
    plot.reset_view()
    assert plot.plotItem.vb.state["autoRange"][0] is not False


def test_small_axis_values_are_not_rescaled_with_an_si_prefix(qtbot):
    """0.067 h on a time axis must not read as 67 under a "(x0.001)" label."""
    plot = CompactPlot()
    plot.plot([0.0, 0.03, 0.067], [150.0, 160.0, 154.0])
    plot.setLabel("bottom", "Time since start (h)")
    qtbot.addWidget(plot)
    plot.show()

    for side in ("left", "bottom"):
        assert plot.getAxis(side).autoSIPrefix is False
    label = plot.getAxis("bottom").labelString()
    assert "Time since start (h)" in label
    assert "x0.001" not in label
