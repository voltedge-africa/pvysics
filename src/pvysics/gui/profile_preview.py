"""The preview of a staged fetched profile: where it came from, G and T charts over the whole range, the
statistics and the checks it passed.

Use profile and Discard emit a signal and close the dialog. Closing it any other way (Close, Escape or
the window's close button) leaves the profile staged. The panel that opened the preview does the rest.

The charts take their colours from the theme palette and restyle when the theme changes. Their time
axis runs from the first sample: a tick at each midnight when the range is days long, with the time of
day between ticks when they are closer than a day.
"""

from datetime import timedelta

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pvysics.fetch import FetchOptions, Irradiance, TimeStandard
from pvysics.gui.palette import Palette
from pvysics.gui.theme import ThemeManager, style_plot
from pvysics.profile import Profile
from pvysics.profile_stats import ProfileStats, plot_indices, profile_stats

PLOT_LINES = 8  # a chart is never shorter than this many text lines, as on the Dashboard
HOURS_PER_DAY = 24.0
MINUTES_PER_HOUR = 60
TICK_STEPS_H = (12.0, 24.0, 72.0, 168.0)  # the tick spacing in hours: round clock times, then days and weeks
MAX_TICKS = 10  # the smallest step that keeps a range to this many ticks is used
CHECKS_PASSED = (
    "the request: latitude and longitude in range, dates in order, none in the future, at most 31 days",
    "no missing values: none blank, not a number, not finite or -999",
    "no negative irradiance",
    "times increase in one constant step, so there are no gaps",
)
IRRADIANCE_TEXT = {Irradiance.ALL_SKY: "all-sky", Irradiance.CLEAR_SKY: "clear-sky"}
STANDARD_TEXT = {TimeStandard.LOCAL: "local standard time (LST)", TimeStandard.UTC: "UTC"}


class TimeAxis(pg.AxisItem):
    """The bottom axis, in hours from the first sample, labelled with dates and times of day.

    The ticks fall on round clock times (every 12 hours for a few days, then every day, every three days
    or every week), so the labels read as dates and not as 20 hour steps from the first sample.
    """

    def __init__(self, origin: np.datetime64) -> None:
        super().__init__("bottom")
        self._origin = origin.astype("datetime64[s]").item()

    def tickValues(self, minVal, maxVal, size):
        span = maxVal - minVal
        step = next((s for s in TICK_STEPS_H if span / s <= MAX_TICKS), TICK_STEPS_H[-1])
        first = np.ceil(minVal / step) * step
        return [(step, np.arange(first, maxVal, step).tolist())]

    def tickStrings(self, values, scale, spacing) -> list[str]:
        pattern = "%d %b" if spacing >= HOURS_PER_DAY else "%d %b %H:%M"
        return [
            (self._origin + timedelta(minutes=round(float(value) * MINUTES_PER_HOUR))).strftime(pattern)
            for value in values
        ]


def _chart(left_label: str, origin: np.datetime64, minimum_height: int) -> pg.PlotWidget:
    plot = pg.PlotWidget(axisItems={"bottom": TimeAxis(origin)})
    for side in ("left", "bottom"):
        plot.getAxis(side).enableAutoSIPrefix(False)  # 900 W/m2 must not show as 0.9 kW/m2
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.setLabel("left", left_label)
    plot.setLabel("bottom", "Date and time")
    plot.setMinimumHeight(minimum_height)
    return plot


def source_text(options: FetchOptions, from_cache: bool) -> str:
    """One line: where the profile came from, the dates, the irradiance, the time standard, and the cache or network."""
    days = (options.end - options.start).days + 1
    where = "from cache" if from_cache else "from the network"
    return (
        f"Source: NASA POWER at latitude {options.latitude:g}, longitude {options.longitude:g}; "
        f"{options.start.isoformat()} to {options.end.isoformat()} ({days} days); "
        f"{IRRADIANCE_TEXT[options.irradiance]} irradiance; time standard {STANDARD_TEXT[options.time_standard]}; "
        f"{where}."
    )


def _step_text(step_s: float) -> str:
    if step_s % 3600 == 0:
        return f"{step_s / 3600:g} h"
    if step_s % 60 == 0:
        return f"{step_s / 60:g} min"
    return f"{step_s:g} s"


def _stamp(stamp: np.datetime64) -> str:
    return np.datetime_as_string(stamp, unit="m").replace("T", " ")


def _text(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)  # a long value wraps rather than widening the dialog
    return label


class ProfilePreview(QDialog):
    """The preview of one staged profile. Opened as a window-modal dialog by the fetch panel."""

    use_requested = pyqtSignal()
    discard_requested = pyqtSignal()

    def __init__(
        self,
        profile: Profile,
        options: FetchOptions,
        from_cache: bool,
        theme: ThemeManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preview fetched profile")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # the dialog goes when it closes; the panel forgets it
        self.resize(960, 640)
        self._stats: ProfileStats = profile_stats(profile)
        self._build(profile, options, from_cache)
        theme.changed.connect(self._apply_palette)  # a bound method, so the connection ends with this dialog
        self._apply_palette(theme.palette)

    @property
    def stats(self) -> ProfileStats:
        return self._stats

    @property
    def irradiance_curve(self) -> pg.PlotDataItem:
        return self._irradiance

    @property
    def temperature_curve(self) -> pg.PlotDataItem:
        return self._temperature

    def _apply_palette(self, palette: Palette) -> None:
        for plot in (self.irradiance_plot, self.temperature_plot):
            style_plot(plot, palette)
        self._irradiance.setPen(pg.mkPen(palette.irradiance, width=2))
        self._temperature.setPen(pg.mkPen(palette.temperature, width=2))

    def _on_use_clicked(self, *_args) -> None:
        self.use_requested.emit()
        self.accept()

    def _on_discard_clicked(self, *_args) -> None:
        self.discard_requested.emit()
        self.accept()

    def _build(self, profile: Profile, options: FetchOptions, from_cache: bool) -> None:
        origin = profile.timestamps[0]
        minimum = self.fontMetrics().height() * PLOT_LINES
        self.irradiance_plot = _chart("Irradiance G (W/m²)", origin, minimum)
        self.temperature_plot = _chart("Temperature T (°C)", origin, minimum)
        self.temperature_plot.setXLink(self.irradiance_plot)
        index = plot_indices(len(profile.timestamps))  # the chart draws a bounded number of points; the stats do not
        hours = (profile.timestamps[index] - origin) / np.timedelta64(1, "h")
        self._irradiance = self.irradiance_plot.plot(hours, profile.irradiance[index])
        self._temperature = self.temperature_plot.plot(hours, profile.temperature[index])

        charts = QVBoxLayout()
        charts.addWidget(self.irradiance_plot, 1)
        charts.addWidget(self.temperature_plot, 1)

        stats = self._stats
        stats_box = QGroupBox("Statistics")
        form = QFormLayout(stats_box)
        form.addRow("Samples", _text(f"{stats.samples}, every {_step_text(stats.step_s)}"))
        form.addRow("First sample", _text(_stamp(stats.first)))
        form.addRow("Last sample", _text(_stamp(stats.last)))
        form.addRow("Days", _text(str(stats.days)))
        form.addRow("Peak G", _text(f"{stats.peak_g:,.0f} W/m² at {_stamp(stats.peak_g_at)}"))
        form.addRow("Daylight samples", _text(f"{stats.daylight_samples} with G above zero"))
        form.addRow(
            "Mean daily energy", _text(f"{stats.mean_daily_energy_wh_m2:,.0f} Wh/m² per day")
        )
        form.addRow(
            "Temperature T",
            _text(f"mean {stats.mean_t:.1f} °C, min {stats.min_t:.1f} °C, max {stats.max_t:.1f} °C"),
        )
        daily = ", ".join(f"{day:%d %b} {peak:,.0f}" for day, peak in stats.daily_peak_g)
        form.addRow("Daily peak G (W/m²)", _text(daily))

        checks_box = QGroupBox("Checks passed")
        QVBoxLayout(checks_box).addWidget(_text("\n".join(f"- {check}" for check in CHECKS_PASSED)))

        side = QVBoxLayout()
        side.addWidget(stats_box)
        side.addWidget(checks_box)
        side.addStretch(1)

        body = QHBoxLayout()
        body.addLayout(charts, 3)
        body.addLayout(side, 2)

        buttons = QDialogButtonBox()
        self.use_button = buttons.addButton("Use profile", QDialogButtonBox.ButtonRole.AcceptRole)
        self.discard_button = buttons.addButton("Discard", QDialogButtonBox.ButtonRole.DestructiveRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self.use_button.clicked.connect(self._on_use_clicked)
        self.discard_button.clicked.connect(self._on_discard_clicked)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(_text(source_text(options, from_cache)))
        layout.addLayout(body, 1)
        layout.addWidget(buttons)
