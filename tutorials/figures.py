#!/usr/bin/env python3
"""Figures for the written handbook (docs/tutorial-handbook.typ): SVG plots drawn from the app's own engine.

    tutorials/.venv/bin/python -W ignore tutorials/figures.py       # writes docs/figures/*.svg

No plotting library: a tiny SVG writer, in the series' greens, so the figures match the videos. Every curve is computed by
tutorials/common/pvdata.py (the engine in src/pvysics), so the numbers in the handbook are the numbers the app produces.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import pvdata  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures"
FOREST, MID, LIGHT, PALE, OLIVE, MUTE, INK, LIME = "#1c4a37", "#2f7d5b", "#5fb083", "#a9d6bb", "#5b7d12", "#6b8a7a", "#173d2e", "#8fb81f"
FONT = "font-family='Liberation Sans, Arial, sans-serif'"


class Plot:
    """One set of axes: x_range and y_range in data units, drawn in a W by H pixel box with a margin for labels."""

    def __init__(self, x_range, y_range, width=520, height=300, xlabel="", ylabel="", title="", left=62, bottom=48, top=30, right=18):
        self.x0, self.x1 = x_range
        self.y0, self.y1 = y_range
        self.w, self.h, self.l, self.b, self.t, self.r = width, height, left, bottom, top, right
        self.parts: list[str] = []
        self.xlabel, self.ylabel, self.title = xlabel, ylabel, title

    def px(self, x):
        return self.l + (x - self.x0) / (self.x1 - self.x0) * (self.w - self.l - self.r)

    def py(self, y):
        return self.h - self.b - (y - self.y0) / (self.y1 - self.y0) * (self.h - self.b - self.t)

    def ticks(self, xs, ys, fmt_x="{:g}", fmt_y="{:g}"):
        for x in xs:
            self.parts.append(f"<line x1='{self.px(x):.1f}' y1='{self.py(self.y0):.1f}' x2='{self.px(x):.1f}' y2='{self.py(self.y1):.1f}' stroke='{PALE}' stroke-width='0.6'/>")
            self.parts.append(f"<text x='{self.px(x):.1f}' y='{self.h - self.b + 16}' text-anchor='middle' font-size='11' fill='{MUTE}' {FONT}>{fmt_x.format(x)}</text>")
        for y in ys:
            self.parts.append(f"<line x1='{self.px(self.x0):.1f}' y1='{self.py(y):.1f}' x2='{self.px(self.x1):.1f}' y2='{self.py(y):.1f}' stroke='{PALE}' stroke-width='0.6'/>")
            self.parts.append(f"<text x='{self.l - 8}' y='{self.py(y) + 4:.1f}' text-anchor='end' font-size='11' fill='{MUTE}' {FONT}>{fmt_y.format(y)}</text>")

    def line(self, xs, ys, color=MID, width=2.4, dash=None):
        pts = " ".join(f"{self.px(x):.1f},{self.py(y):.1f}" for x, y in zip(xs, ys))
        d = f" stroke-dasharray='{dash}'" if dash else ""
        self.parts.append(f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='{width}' stroke-linejoin='round'{d}/>")

    def hline(self, y, color=MUTE, dash="5 4", label=None, width=1.2):
        self.parts.append(f"<line x1='{self.px(self.x0):.1f}' y1='{self.py(y):.1f}' x2='{self.px(self.x1):.1f}' y2='{self.py(y):.1f}' stroke='{color}' stroke-width='{width}' stroke-dasharray='{dash}'/>")
        if label:
            self.text(self.x1, y, label, color=color, dx=-4, dy=-5, anchor="end")

    def vline(self, x, color=MUTE, dash="5 4", label=None, dy=12):
        self.parts.append(f"<line x1='{self.px(x):.1f}' y1='{self.py(self.y0):.1f}' x2='{self.px(x):.1f}' y2='{self.py(self.y1):.1f}' stroke='{color}' stroke-width='1.2' stroke-dasharray='{dash}'/>")
        if label:
            self.text(x, self.y1, label, color=color, dx=4, dy=dy, anchor="start")

    def dot(self, x, y, color=LIME, r=5, label=None, dx=8, dy=-8, anchor="start", bold=True):
        self.parts.append(f"<circle cx='{self.px(x):.1f}' cy='{self.py(y):.1f}' r='{r}' fill='{color}' stroke='{FOREST}' stroke-width='1.4'/>")
        if label:
            self.text(x, y, label, color=FOREST, dx=dx, dy=dy, anchor=anchor, bold=bold)

    def text(self, x, y, s, color=INK, size=12, dx=0, dy=0, anchor="middle", bold=False):
        w = " font-weight='bold'" if bold else ""
        self.parts.append(f"<text x='{self.px(x) + dx:.1f}' y='{self.py(y) + dy:.1f}' text-anchor='{anchor}' font-size='{size}' fill='{color}'{w} {FONT}>{s}</text>")

    def svg(self):
        frame = f"<rect x='{self.px(self.x0):.1f}' y='{self.py(self.y1):.1f}' width='{self.px(self.x1) - self.px(self.x0):.1f}' height='{self.py(self.y0) - self.py(self.y1):.1f}' fill='none' stroke='{MUTE}' stroke-width='1.2'/>"
        head = []
        if self.title:
            head.append(f"<text x='{self.l}' y='18' font-size='14' font-weight='bold' fill='{FOREST}' {FONT}>{self.title}</text>")
        if self.xlabel:
            head.append(f"<text x='{(self.px(self.x0) + self.px(self.x1)) / 2:.1f}' y='{self.h - 8}' text-anchor='middle' font-size='12' fill='{INK}' {FONT}>{self.xlabel}</text>")
        if self.ylabel:
            head.append(f"<text transform='translate(14 {(self.py(self.y0) + self.py(self.y1)) / 2:.1f}) rotate(-90)' text-anchor='middle' font-size='12' fill='{INK}' {FONT}>{self.ylabel}</text>")
        return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{self.w}' height='{self.h}' viewBox='0 0 {self.w} {self.h}'>"
                f"<rect width='100%' height='100%' fill='white'/>" + "".join(self.parts) + frame + "".join(head) + "</svg>")

    def save(self, name):
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(self.svg())
        print("wrote", name)


def iv_pv():
    c = pvdata.iv(1000, 25)
    p = Plot((0, 40), (0, 10), xlabel="Voltage (V)", ylabel="Current (A)", title="I-V curve at 1000 W/m2, 25 C", width=520, height=300)
    p.ticks(range(0, 41, 10), range(0, 11, 2))
    p.line(c.voltage, c.current, MID)
    p.dot(0, c.current[0], label=f"Isc = {c.current[0]:.1f} A", dx=10, dy=-10)
    p.dot(c.voltage[-1], 0, label=f"Voc = {c.voltage[-1]:.1f} V", dx=-8, dy=-12, anchor="end")
    p.dot(c.mpp_voltage, c.mpp_current, label=f"MPP {c.mpp_voltage:.1f} V, {c.mpp_current:.1f} A", dx=10, dy=-10)
    p.save("iv-curve.svg")
    q = Plot((0, 40), (0, 280), xlabel="Voltage (V)", ylabel="Power (W)", title="P-V curve (power = voltage x current)", width=520, height=300)
    q.ticks(range(0, 41, 10), range(0, 281, 70))
    q.line(c.voltage, c.power, FOREST)
    q.dot(c.mpp_voltage, c.mpp_power, label=f"maximum power {c.mpp_power:.1f} W", dx=-10, dy=-10, anchor="end")
    q.save("pv-curve.svg")


def sun_and_heat():
    shades = [FOREST, MID, LIGHT, OLIVE]
    p = Plot((0, 40), (0, 10), xlabel="Voltage (V)", ylabel="Current (A)", title="Less sun: the curve shrinks in height", width=520, height=300)
    p.ticks(range(0, 41, 10), range(0, 11, 2))
    for g, col in zip((1000, 800, 500, 200), shades):
        c = pvdata.iv(g, 25)
        p.line(c.voltage, c.current, col)
        p.text(c.voltage[-1] - 0.5, c.current[0] + 0.45, f"{g} W/m2", color=col, size=11, anchor="end", bold=True)
    p.save("sun-family.svg")
    q = Plot((0, 40), (0, 10), xlabel="Voltage (V)", ylabel="Current (A)", title="More heat: the curve shrinks in width", width=520, height=300)
    q.ticks(range(0, 41, 10), range(0, 11, 2))
    for t, col in zip((25, 45, 65), (FOREST, MID, OLIVE)):
        c = pvdata.iv(1000, t)
        q.line(c.voltage, c.current, col)
        q.text(c.voltage[-1] + 0.3, 1.0 + (t - 25) * 0.02, f"{t} C", color=col, size=11, anchor="start", bold=True)
    q.save("heat-family.svg")


def faults():
    kinds = [(pvdata.FaultKind.PARTIAL_SHADING, "Partial shading"), (pvdata.FaultKind.SOILING, "Soiling"),
             (pvdata.FaultKind.SERIES_RESISTANCE_RISE, "Series resistance rise"), (pvdata.FaultKind.DIODE_FAILURE, "Bypass diode failure")]
    for kind, title in kinds:
        healthy, faulty = pvdata.fault_iv(kind)
        p = Plot((0, 40), (0, 10), xlabel="Voltage (V)", ylabel="Current (A)", title=f"{title}: {faulty.mpp_power:.0f} W instead of {healthy.mpp_power:.0f} W", width=400, height=250)
        p.ticks(range(0, 41, 10), range(0, 11, 2))
        p.line(healthy.voltage, healthy.current, MID, dash="6 4")
        p.line(faulty.voltage, faulty.current, OLIVE)
        p.dot(faulty.mpp_voltage, faulty.mpp_current, color=LIME, r=4)
        p.save(f"fault-{kind.name.lower()}.svg")


def day():
    healthy = pvdata.day()
    shaded = pvdata.day(pvdata.FaultKind.PARTIAL_SHADING, 11.0)
    p = Plot((0, 23), (0, 125), xlabel="Hours since midnight", ylabel="Power (W)", title="Shading at 11:00: measured power falls away", width=560, height=300)
    p.ticks(range(0, 24, 4), range(0, 126, 25))
    p.line(shaded.hours, shaded.predicted, MID, dash="7 4")
    p.line(shaded.hours, shaded.measured, INK, width=2)
    p.vline(11, color=OLIVE, label="shading injected")
    p.text(2.2, 108, "measured", color=INK, size=12, anchor="start", bold=True)
    p.text(2.2, 94, "predicted (twin)", color=MID, size=12, anchor="start", bold=True)
    p.save("day-shading.svg")
    q = Plot((0, 23), (-40, 10), xlabel="Hours since midnight", ylabel="Deviation (%)", title="The deviation crosses both limits", width=560, height=250)
    q.ticks(range(0, 24, 4), (-40, -30, -20, -10, -5, 0, 5, 10))
    q.hline(-5, color=LIGHT, label="warning -5 %")
    q.hline(-10, color=OLIVE, label="abnormal -10 %")
    mask = shaded.predicted >= 5
    q.line(shaded.hours[mask], shaded.deviation[mask], FOREST, width=2)
    q.save("day-deviation.svg")
    h = Plot((0, 23), (-6, 6), xlabel="Hours since midnight", ylabel="Deviation (%)", title="A healthy day: the deviation stays near zero", width=560, height=230)
    h.ticks(range(0, 24, 4), (-5, 0, 5))
    h.hline(5, color=LIGHT)
    h.hline(-5, color=LIGHT, label="limits +/-5 %")
    m = healthy.predicted >= 5
    h.line(healthy.hours[m], healthy.deviation[m], FOREST, width=1.6)
    h.save("day-healthy.svg")


def histogram():
    """The size of the healthy day's deviation, as Settings > Limits > Derive from healthy run computes it (seed 0)."""
    healthy = pvdata.day(seed=0)
    dev = np.abs(healthy.deviation[healthy.predicted >= 5])
    mean, sd = float(dev.mean()), float(dev.std())
    bins = np.arange(0.0, 2.51, 0.125)
    counts, _ = np.histogram(dev, bins=bins)
    p = Plot((0, 2.5), (0, counts.max() * 1.15), xlabel="Size of the deviation (%)", ylabel="Daylight samples",
             title="Healthy day: size of the deviation, and the derived limits", width=560, height=280)
    p.ticks([0, 0.5, 1.0, 1.5, 2.0, 2.5], [int(v) for v in np.linspace(0, counts.max(), 5)])
    for left, c in zip(bins[:-1], counts):
        p.parts.append(f"<rect x='{p.px(left) + 1:.1f}' y='{p.py(c):.1f}' width='{p.px(left + 0.125) - p.px(left) - 2:.1f}' height='{p.py(0) - p.py(c):.1f}' fill='{LIGHT}'/>")
    for row, (k, col, name) in enumerate(((0, MUTE, "mean"), (2, MID, "warning = mean + 2 sd"), (3, OLIVE, "abnormal = mean + 3 sd"))):
        x = mean + k * sd
        p.vline(x, color=col, label=f"{name} = {x:.2f} %", dy=12 + 15 * row)
    print(f"histogram: mean {mean:.2f}, warning {mean + 2 * sd:.2f}, abnormal {mean + 3 * sd:.2f}, above warning {(dev > mean + 2 * sd).mean() * 100:.1f} %")
    p.save("healthy-histogram.svg")


if __name__ == "__main__":
    iv_pv()
    sun_and_heat()
    faults()
    day()
    histogram()
