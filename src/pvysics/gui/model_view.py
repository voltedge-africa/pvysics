"""The HMI Model view: the Single Diode Model circuit and equations, the parameters the twin uses,
live inputs and outputs, and the I-V and P-V curves with the measured operating point.

Layout follows the model wireframe: circuit and equations on top, parameters, live inputs and
outputs in the middle, the curves below. The schematic and equations keep their aspect ratio and
scale with the window; the equation images sit on white cards so they read on any window colour.
The curves are for the measured G and T of the latest Sample. They are recomputed at most once per
UI tick, and only when G or T has moved since the curve was last computed.
"""

from importlib.resources import files

import pyqtgraph as pg
from PyQt6.QtCore import QByteArray, QRectF, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from pvysics.gui.data_bus import DataBus
from pvysics.gui.playback import PlaybackController
from pvysics.gui.process_view import ReadingsPanel, format_number, format_readings
from pvysics.run import Sample
from pvysics.single_diode import DiodeParameters, IVCurve, fit_parameters, solve_curve

UI_INTERVAL_MS = 100  # the Model view refreshes at most this often, as the Dashboard does
SCHEMATIC = "circuit_sdm.svg"
EQUATION_IMAGES = ("eq_sdm.png", "eq_iph.png", "eq_vt.png")  # top to bottom
CARD_COLOUR = "#ffffff"
CARD_BORDER_COLOUR = "#bdbdbd"
CURVE_COLOUR = "#1565c0"
POWER_COLOUR = "#ef6c00"
POINT_COLOUR = "#c62828"

PARAMETER_ROWS = [
    ("iph", "Iph at STC"),
    ("rs", "Rs"),
    ("rsh", "Rsh"),
    ("n", "n (ideality)"),
    ("ns", "Ns (cells)"),
]
DATASHEET_ROWS = [("isc", "Isc"), ("voc", "Voc"), ("impp", "Impp"), ("vmpp", "Vmpp")]
LIVE_ROWS = [("G", "Irradiance G"), ("T", "Module temp T"), ("VI", "Measured V, I")]
OUTPUT_ROWS = [("p_pred", "P predicted"), ("p_mpp", "Model Pmpp"), ("deviation", "Deviation")]


def _asset(name: str) -> bytes:
    """The bytes of a design asset packaged under pvysics/gui/assets."""
    return (files("pvysics") / "gui" / "assets" / name).read_bytes()


def fitted_rect(area: QRectF, aspect: float) -> QRectF:
    """The largest rectangle of width-to-height `aspect` that fits in area, centred."""
    width = min(area.width(), area.height() * aspect)
    height = width / aspect
    centre = area.center()
    return QRectF(centre.x() - width / 2, centre.y() - height / 2, width, height)


class CircuitWidget(QWidget):
    """The Single Diode Model schematic: an SVG drawn at its own aspect ratio, scaled to fit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(QByteArray(_asset(SCHEMATIC)))
        view_box = self._renderer.viewBoxF()
        self._aspect = view_box.width() / view_box.height()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(self.fontMetrics().height() * 8, self.fontMetrics().height() * 4)

    @property
    def aspect(self) -> float:
        return self._aspect

    def drawn_rect(self) -> QRectF:
        """Where the schematic is drawn inside the widget."""
        return fitted_rect(QRectF(self.rect()), self._aspect)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        self._renderer.render(painter, self.drawn_rect())
        painter.end()


class EquationsWidget(QWidget):
    """The three typeset equations, stacked on white cards at one common scale.

    The images have transparent backgrounds, so each sits on a card to stay legible on any
    window colour. A common scale keeps the type sizes of the three images consistent.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._images: list[QPixmap] = []
        for name in EQUATION_IMAGES:
            image = QPixmap()
            if not image.loadFromData(_asset(name)):
                raise ValueError(f"cannot load the equation image {name}")
            self._images.append(image)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(self.fontMetrics().height() * 16, self.fontMetrics().height() * 9)

    def picture_rects(self) -> list[QRectF]:
        """Where each equation image is drawn, top to bottom, inside its card."""
        pad = self.fontMetrics().height() / 2
        gap = pad
        widest = max(image.width() for image in self._images)
        total_height = sum(image.height() for image in self._images)
        area = QRectF(self.rect()).adjusted(pad, pad, -pad, -pad)
        scale = min(
            (area.width() - 2 * pad) / widest,
            (area.height() - 2 * pad * len(self._images) - gap * (len(self._images) - 1))
            / total_height,
        )
        scale = max(scale, 0.0)
        used = total_height * scale + 2 * pad * len(self._images) + gap * (len(self._images) - 1)
        top = area.top() + (area.height() - used) / 2
        rects = []
        for image in self._images:
            width = image.width() * scale
            height = image.height() * scale
            left = area.center().x() - width / 2
            rects.append(QRectF(left, top + pad, width, height))
            top += height + 2 * pad + gap
        return rects

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pad = self.fontMetrics().height() / 2
        painter.setPen(QPen(QColor(CARD_BORDER_COLOUR)))
        painter.setBrush(QBrush(QColor(CARD_COLOUR)))
        for image, picture in zip(self._images, self.picture_rects()):
            card = picture.adjusted(-pad, -pad, pad, pad)
            painter.drawRoundedRect(card, pad / 3, pad / 3)
            painter.drawPixmap(picture, image, QRectF(image.rect()))
        painter.end()


def _curve_plot(left_label: str) -> pg.PlotWidget:
    plot = pg.PlotWidget()
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.setLabel("left", left_label)
    plot.setLabel("bottom", "Voltage (V)")
    return plot


class ModelView(QWidget):
    """The Model screen. Shows the twin's model for the measured G and T of the latest Sample."""

    def __init__(self, controller: PlaybackController, bus: DataBus, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        self._datasheet = controller.config.datasheet
        self._parameters = fit_parameters(self._datasheet)  # the same fit the twin predicts with
        self._sample: Sample | None = None
        self._dirty = False
        self._curve: IVCurve | None = None
        self._curve_key: tuple[float, float] | None = None
        self._point: tuple[float, float] | None = None

        self.parameter_panel = ReadingsPanel("Parameters in use", PARAMETER_ROWS)
        self.datasheet_panel = ReadingsPanel("Module datasheet", DATASHEET_ROWS)
        self.live_panel = ReadingsPanel("Live inputs", LIVE_ROWS)
        self.output_panel = ReadingsPanel("Outputs", OUTPUT_ROWS)
        self._show_parameters()

        self.circuit = CircuitWidget()
        self.equations = EquationsWidget()
        self.iv_plot = _curve_plot("Current (A)")
        self.pv_plot = _curve_plot("Power (W)")
        self._iv_curve = self.iv_plot.plot(pen=pg.mkPen(CURVE_COLOUR, width=2))
        self._pv_curve = self.pv_plot.plot(pen=pg.mkPen(POWER_COLOUR, width=2))
        self._iv_point = _point_item(self.iv_plot)
        self._pv_point = _point_item(self.pv_plot)

        self._build_layout()
        self._show_start()

        bus.sample.connect(self._on_sample)
        bus.run_reset.connect(self._on_reset)
        self._timer = QTimer(self)
        self._timer.setInterval(UI_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    @property
    def parameters(self) -> DiodeParameters:
        """The parameters the twin predicts with: the fit to the run's datasheet."""
        return self._parameters

    @property
    def curve(self) -> IVCurve | None:
        """The model curve for the measured G and T on show, or None before a run has a Sample."""
        return self._curve

    @property
    def curve_key(self) -> tuple[float, float] | None:
        """The measured (G, T) the curve was computed for."""
        return self._curve_key

    @property
    def operating_point(self) -> tuple[float, float] | None:
        """The measured (V, I) drawn on the curves, or None before a run has a Sample."""
        return self._point

    def refresh(self) -> None:
        """The UI tick: show the latest Sample. The curve is recomputed only when G or T moved.

        Does nothing while the view is hidden or when no new Sample has arrived.
        """
        if not self._dirty or not self.isVisible() or self._sample is None:
            return
        self._dirty = False
        sample = self._sample
        key = (sample.measured_irradiance, sample.measured_temperature)
        if key != self._curve_key:
            self._curve = solve_curve(self._datasheet, key[0], key[1], self._parameters)
            self._curve_key = key
            self._plot_curve()
        self._point = (sample.measured_voltage, sample.measured_current)
        self._show_point(sample)
        self._show_values(sample)

    def _on_sample(self, sample: Sample) -> None:
        self._sample = sample
        self._dirty = True

    def _on_reset(self) -> None:
        """A new run may bring another module: refit the parameters the twin predicts with."""
        self._datasheet = self._controller.config.datasheet
        self._parameters = fit_parameters(self._datasheet)
        self._show_parameters()
        self._show_start()

    def _show_parameters(self) -> None:
        p, ds = self._parameters, self._datasheet
        self.parameter_panel.set_values(
            {
                "iph": f"{format_number(p.photocurrent_stc_a, 2)} A",
                "rs": f"{format_number(p.series_resistance_ohm, 3)} Ω",
                "rsh": f"{format_number(p.shunt_resistance_ohm, 1)} Ω",
                "n": format_number(p.ideality, 2),
                "ns": str(ds.ns),
            }
        )
        self.datasheet_panel.set_values(
            {
                "isc": f"{format_number(ds.isc_a, 2)} A",
                "voc": f"{format_number(ds.voc_v, 2)} V",
                "impp": f"{format_number(ds.impp_a, 2)} A",
                "vmpp": f"{format_number(ds.vmpp_v, 2)} V",
            }
        )

    def _show_values(self, sample: Sample) -> None:
        readings = format_readings(sample)
        self.live_panel.set_values(
            {"G": readings["G"], "T": readings["T"], "VI": f"{readings['V']}, {readings['I']}"}
        )
        self.output_panel.set_values(
            {
                "p_pred": readings["P_pred"],
                "p_mpp": f"{format_number(self._curve.mpp_power, 1)} W",
                "deviation": f"{format_number(sample.deviation_pct, 1, signed=True)} %",
            }
        )

    def _show_point(self, sample: Sample) -> None:
        voltage, current = self._point
        self._iv_point.setData([voltage], [current])
        self._pv_point.setData([voltage], [sample.power_measured])

    def _plot_curve(self) -> None:
        self._iv_curve.setData(self._curve.voltage, self._curve.current)
        self._pv_curve.setData(self._curve.voltage, self._curve.power)

    def _show_start(self) -> None:
        self._sample = None
        self._dirty = False
        self._curve = None
        self._curve_key = None
        self._point = None
        self._iv_curve.setData([], [])
        self._pv_curve.setData([], [])
        self._iv_point.setData([], [])
        self._pv_point.setData([], [])
        self.live_panel.clear()
        self.output_panel.clear()

    def _build_layout(self) -> None:
        circuit_box = QGroupBox("Single diode model")
        QVBoxLayout(circuit_box).addWidget(self.circuit)
        equations_box = QGroupBox("Equations")
        QVBoxLayout(equations_box).addWidget(self.equations)

        top = QHBoxLayout()
        top.addWidget(circuit_box, 1)
        top.addWidget(equations_box, 1)

        readings = QHBoxLayout()
        for panel in (self.parameter_panel, self.datasheet_panel, self.live_panel, self.output_panel):
            readings.addWidget(panel, 1)

        curves_box = QGroupBox("I-V and P-V curve at the measured G and T")
        curves = QHBoxLayout(curves_box)
        curves.addWidget(self.iv_plot, 1)
        curves.addWidget(self.pv_plot, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top, 3)
        layout.addLayout(readings)
        layout.addWidget(curves_box, 3)


def _point_item(plot: pg.PlotWidget) -> pg.ScatterPlotItem:
    """The measured operating point, drawn on top of a curve."""
    point = pg.ScatterPlotItem(size=12, brush=pg.mkBrush(POINT_COLOUR), pen=pg.mkPen(None))
    point.setZValue(10)
    plot.addItem(point)
    return point
