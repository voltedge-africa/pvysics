"""PV Digital Twin, Tutorial 3: The plant and its faults: scenes.

Every curve comes from the app's engine (common/pvdata.py, and pvysics.run for the plant's mismatch and the noise-free sensor run).
"""
import functools
from dataclasses import replace

import numpy as np

from common import *
from pvysics.run import _plant

FAULT = pvdata.FaultKind


# ------------------------------------------------------------------ data (engine runs are cached per process)
@functools.lru_cache(maxsize=None)
def healthy_day():
    return pvdata.day()


@functools.lru_cache(maxsize=None)
def faulty_day(kind):
    return pvdata.day(kind, 11.0)


@functools.lru_cache(maxsize=None)
def clean_irradiance():
    """The same day with the irradiance sensor's noise switched off: the engine run once more."""
    cfg = pvdata.bundled_run_config(seed=1)
    cfg = replace(cfg, sensors=replace(cfg.sensors, irradiance_noise_pct=0.0))
    return np.array([s.measured_irradiance for s in pvdata.run(cfg).samples])


@functools.lru_cache(maxsize=None)
def twin_and_plant():
    """The twin's curve and the plant's curve at 1000 W/m2 and 25 C (the plant has the engine's mismatch applied)."""
    twin = pvdata.iv(1000.0, 25.0)
    sheet, params = _plant(pvdata.bundled_run_config(seed=1))
    return twin, pvdata.solve_curve(sheet, 1000.0, 25.0, params)


# ------------------------------------------------------------------ drawing helpers
def graph(x_range, y_range, width, height, center, x_label=None, y_label=None, numbers=True, x_numbers=True):
    """Axes with optional labels. Returns a VGroup; `.ax` is the Axes (use ax.c2p for points).
    x_numbers=False drops the x numbers (use hour_ticks) when the x axis sits on y = 0 inside the plot."""
    ax = Axes(x_range=x_range, y_range=y_range, x_length=width, y_length=height, tips=False,
              axis_config={"color": MUTE, "include_ticks": False, "include_numbers": numbers, "font_size": 20})
    ax.move_to(center)
    if numbers:
        for axis in (ax.x_axis, ax.y_axis):
            axis.numbers.set_color(MUTE)
        if not x_numbers:
            ax.x_axis.remove(ax.x_axis.numbers)
    out = VGroup(ax)
    if x_label:
        out.add(label(x_label, size=20, color=MUTE).next_to(ax, DOWN, buff=0.55))
    if y_label:
        out.add(label(y_label, size=20, color=MUTE).next_to(ax, UP, buff=0.12).align_to(ax, LEFT))
    out.ax = ax
    return out


def hour_ticks(ax, hours, y):
    """Hour labels under the plot at height y (for axes whose x axis is drawn at y = 0)."""
    return VGroup(*[label(f"{h}", size=20, color=MUTE).next_to(ax.c2p(h, y), DOWN, buff=0.08) for h in hours])


def stairs(ax, xs, ys, **kw):
    """Step line through (xs, ys): horizontal, then vertical at each sample."""
    pts = []
    for i in range(len(xs)):
        if i:
            pts.append(ax.c2p(xs[i], ys[i - 1]))
        pts.append(ax.c2p(xs[i], ys[i]))
    return polyline(pts, **kw)


def node(lines, w, h, color=FOREST):
    """Box with one or more text lines (the first is bold)."""
    box = RoundedRectangle(corner_radius=0.12, width=w, height=h, stroke_color=color, stroke_width=4,
                           fill_color=WHITE, fill_opacity=1)
    texts = VGroup(*[label(s, size=24, color=FOREST, weight=BOLD) if i == 0 else label(s, size=21, color=INK)
                     for i, s in enumerate(lines)]).arrange(DOWN, buff=0.08)
    texts.move_to(box)
    return VGroup(box, texts)


def link(a, b, color=FOREST):
    return Arrow(a.get_right(), b.get_left(), buff=0.08, color=color, stroke_width=4, max_tip_length_to_length_ratio=0.2)


def result_row(y, name, value, change, color=OLIVE):
    return VGroup(label(name, size=22, color=INK).move_to([-5.9, y, 0], aligned_edge=LEFT),
                  label(value, size=22, color=INK).move_to([-1.3, y, 0], aligned_edge=LEFT),
                  label(change, size=22, color=color, weight=BOLD).move_to([3.7, y, 0], aligned_edge=LEFT))


def pct_text(pct):
    return "0 %" if round(pct) == 0 else f"{pct:+.0f} %"


# ------------------------------------------------------------------ scenes
class Plant(Narrated):
    scene_id = "plant"

    def construct(self):
        n = self.n
        self.header()
        twin = pvdata.diode_parameters()
        sheet = pvdata.module()
        name_x, twin_x, plant_x = -5.9, 1.2, 5.2
        head_y = 1.9
        head = VGroup(
            label("parameter", size=22, color=MUTE).move_to([name_x, head_y, 0], aligned_edge=LEFT),
            label("twin (datasheet)", size=24, color=FOREST, weight=BOLD).move_to([twin_x, head_y, 0]),
            label("plant", size=24, color=FOREST, weight=BOLD).move_to([plant_x, head_y, 0]),
        )
        rule = Line([-6.4, 1.4, 0], [6.4, 1.4, 0], color=MID, stroke_width=3)
        spec = [
            ("series resistance Rs", f"{twin.series_resistance_ohm:.3f} Ω", "+3 % higher"),
            ("shunt resistance Rsh", f"{twin.shunt_resistance_ohm:.0f} Ω", "+5 % higher"),
            ("voltage coefficient Kv", f"{sheet.kv_pct_per_c:.2f} %/°C", "+2 % off"),
        ]
        rows = []
        for i, (name, tv, pv) in enumerate(spec):
            y = 0.5 - i * 1.0
            rows.append(VGroup(label(name, size=26, color=INK).move_to([name_x, y, 0], aligned_edge=LEFT),
                               label(tv, size=28, color=INK).move_to([twin_x, y, 0]),
                               label(pv, size=28, color=FOREST, weight=BOLD).move_to([plant_x, y, 0])))
        table = VGroup(head, rule, *rows)

        self.at(n.start(0), FadeIn(head), Create(rule), run_time=0.9)
        self.at(n.cue(0, "series"), FadeIn(rows[0], shift=RIGHT * 0.2))
        self.at(n.cue(0, "shunt"), FadeIn(rows[1], shift=RIGHT * 0.2))
        self.at(n.cue(0, "coefficient"), FadeIn(rows[2], shift=RIGHT * 0.2))

        # noise and rounding: a noon zoom of irradiance, and eight voltage samples at the sensor step
        d = healthy_day()
        clean = clean_irradiance()
        win = (d.hours >= 12.0) & (d.hours <= 12.2)
        xs = d.hours[win]
        lo = min(clean[win].min(), d.irradiance[win].min()) - 3
        hi = max(clean[win].max(), d.irradiance[win].max()) + 3
        g = graph([12.0, 12.2], [lo, hi], 7.4, 3.6, center=[-2.6, 0.2, 0], y_label="irradiance (W/m²)", numbers=False)
        g.add(label("12:00 to 12:12", size=20, color=MUTE).next_to(g.ax, DOWN, buff=0.3))
        smooth = trace(g.ax, xs, clean[win], color=MID, stroke_width=5)
        noisy = trace(g.ax, xs, d.irradiance[win], color=INK, stroke_width=4)
        i0 = int(np.argmax(d.hours >= 12.0))
        vals = d.voltage[i0:i0 + 8]
        z = graph([0, 7, 1], [vals.min() - 0.004, vals.max() + 0.004], 3.6, 3.0, center=[4.6, 0.2, 0],
                  y_label="voltage (V)", numbers=False)
        z.add(label("steps of 0.004 V", size=20, color=MUTE).next_to(z.ax, DOWN, buff=0.3))
        zstep = stairs(z.ax, np.arange(len(vals)), vals, color=MID, stroke_width=4)
        zdots = VGroup(*[Dot(z.ax.c2p(i, v), radius=0.06, color=INK) for i, v in enumerate(vals)])

        self.at(n.start(1), FadeOut(table), FadeIn(g), Create(smooth), run_time=1.0)
        self.at(n.cue(1, "noise"), Transform(smooth, noisy), run_time=1.2)
        self.at(n.cue(1, "rounded"), FadeIn(z), Create(zstep), FadeIn(zdots), run_time=0.9)
        beat1_objects = VGroup(g, smooth, z, zstep, zdots)

        # identical: the twin and the plant overlap; the deviation is a flat zero line; then it separates slightly
        twin_c, plant_c = twin_and_plant()
        pv = graph([0, 40, 10], [0, 300, 50], 9.0, 2.5, center=[0, 0.7, 0], y_label="power (W)")
        dv = graph([0, 40, 10], [-4, 4, 2], 9.0, 1.4, center=[0, -2.1, 0], numbers=False)
        zero = Line(dv.ax.c2p(0, 0), dv.ax.c2p(40, 0), color=MUTE, stroke_width=3)
        zero_label = label("deviation 0: nothing to learn", size=20, color=OLIVE, weight=BOLD).move_to(dv.ax.c2p(24, 2.6))
        v = np.linspace(0, min(twin_c.voltage[-1], plant_c.voltage[-1]), 400)
        tw_p = np.interp(v, twin_c.voltage, twin_c.power)
        pl_p = np.interp(v, plant_c.voltage, plant_c.power)
        keep = tw_p > 5
        dev = np.clip((pl_p - tw_p)[keep] / tw_p[keep] * 100, -4, 4)
        self.at(n.start(2), FadeOut(beat1_objects), FadeIn(pv), FadeIn(dv), Create(zero), FadeIn(zero_label), run_time=0.9)
        twin_trace = trace(pv.ax, twin_c.voltage, twin_c.power, color=MID, stroke_width=9)
        plant_trace = trace(pv.ax, plant_c.voltage, plant_c.power, color=INK, stroke_width=3)
        dev_trace = trace(dv.ax, v[keep], dev, color=FOREST, stroke_width=4)
        self.at(n.cue(2, "identical"), Create(twin_trace, run_time=1.0), Create(plant_trace, run_time=1.0))
        self.at(n.cue(2, "never"), Create(dev_trace, run_time=1.5))

        # wobble: the deviation of a healthy day, with the +/-5 and +/-10 limits
        m = healthy_day().predicted >= 5
        hrs, dev_day = healthy_day().hours[m], healthy_day().deviation[m]
        dx = graph([5, 18, 1], [-10, 10, 5], 10.5, 3.7, center=[0, -0.3, 0], x_label="time of day (hours)", y_label="deviation (%)",
                   x_numbers=False)
        ax = dx.ax
        dx.add(hour_ticks(ax, range(6, 19, 2), -10))
        limits = VGroup(*[DashedLine(ax.c2p(5, y), ax.c2p(18, y), color=PALE, stroke_width=3, dash_length=0.15)
                          for y in (5, -5, 10, -10)])
        limit_labels = VGroup(*[label(t, size=18, color=MUTE).next_to(ax.c2p(18, y), RIGHT, buff=0.25)
                                for t, y in (("5 %", 5), ("-5 %", -5), ("10 %", 10), ("-10 %", -10))])
        zero_day = Line(ax.c2p(5, 0), ax.c2p(18, 0), color=MUTE, stroke_width=2)
        largest = label(f"largest: {np.abs(dev_day).max():.1f} %", size=24, color=FOREST, weight=BOLD).move_to(ax.c2p(7.0, 7.6), aligned_edge=LEFT)
        trace_day = trace(ax, hrs, dev_day, color=FOREST, stroke_width=4)
        beat2_objects = VGroup(pv, dv, zero, zero_label, twin_trace, plant_trace, dev_trace)
        self.at(n.start(3), FadeOut(beat2_objects), FadeIn(dx), FadeIn(limits), FadeIn(limit_labels),
                FadeIn(zero_day), run_time=0.9)
        self.at(n.cue(3, "wobbles"), Create(trace_day, run_time=2.5, rate_func=linear), FadeIn(largest))
        self.at(n.cue(3, "five"), Indicate(limits[0], color=LIME), Indicate(limits[1], color=LIME))
        self.finish()


class Five(Narrated):
    scene_id = "five"

    def construct(self):
        n = self.n
        self.header()

        def icon_shading():
            mod = Rectangle(width=0.9, height=0.6, stroke_color=MID, stroke_width=3, fill_color=WHITE, fill_opacity=1)
            shade = Rectangle(width=0.45, height=0.6, stroke_width=0, fill_color=INK, fill_opacity=0.45).move_to(mod.get_left() + RIGHT * 0.225)
            return VGroup(mod, shade)

        def icon_soiling():
            mod = Rectangle(width=0.9, height=0.6, stroke_color=MID, stroke_width=3, fill_color=WHITE, fill_opacity=1)
            spots = [(-0.25, 0.1), (0.0, -0.12), (0.22, 0.14), (0.1, 0.2), (-0.3, -0.15), (0.3, -0.1)]
            return VGroup(mod, *[Dot(mod.get_center() + [dx, dy, 0], radius=0.05, color=MUTE) for dx, dy in spots])

        def icon_rs():
            zig = [(-0.45, 0, 0), (-0.3, 0.22, 0), (-0.15, -0.22, 0), (0, 0.22, 0), (0.15, -0.22, 0), (0.3, 0.22, 0), (0.45, 0, 0)]
            return polyline(zig, color=MID, stroke_width=5)

        def icon_diode():
            tri = Triangle(fill_color=MID, fill_opacity=1, stroke_width=0).scale(0.3).rotate(-PI / 2)
            bar = Line([0.22, -0.3, 0], [0.22, 0.3, 0], color=FOREST, stroke_width=6)
            return VGroup(tri, bar)

        def icon_sensor():
            gauge = Arc(radius=0.42, start_angle=0, angle=PI, color=OLIVE, stroke_width=5)
            needle = Line([0, -0.05, 0], [0.26, 0.26, 0], color=OLIVE, stroke_width=5)
            return VGroup(gauge, needle, Dot(ORIGIN, radius=0.06, color=OLIVE))

        specs = [
            (-4.3, 0.9, 1, "Partial shading", "shadow on part of the\nmodule: less light", icon_shading),
            (0.0, 0.9, 2, "Soiling", "dust on the glass:\nless light, evenly", icon_soiling),
            (4.3, 0.9, 3, "Rs increase", "bad connection, loss\nas heat in the wiring", icon_rs),
            (-2.15, -1.3, 4, "Diode failure", "a third of the cells\nout of the circuit", icon_diode),
            (2.15, -1.3, 5, "Sensor drift", "the irradiance sensor\nreads too high", icon_sensor),
        ]
        boxes, contents = [], []
        for x, y, number, title, desc, icon in specs:
            box = card(4.1, 2.0).move_to([x, y, 0])
            num = label(str(number), size=20, color=MUTE).move_to(box.get_corner(UL) + [0.25, -0.25, 0])
            ic = icon().move_to(box.get_left() + RIGHT * 0.7)
            text = VGroup(label(title, size=26, color=FOREST, weight=BOLD), label(desc, size=20, color=INK))
            text.arrange(DOWN, aligned_edge=LEFT, buff=0.2).move_to(box.get_left() + RIGHT * 1.35, aligned_edge=LEFT)
            boxes.append(VGroup(box, num))
            contents.append(VGroup(ic, text))

        self.at(n.start(0), FadeIn(VGroup(*boxes), lag_ratio=0.15), run_time=1.4)
        self.at(n.cue(1, "shading"), FadeIn(contents[0]))
        self.at(n.cue(1, "soiling"), FadeIn(contents[1]))
        self.at(n.cue(2, "resistance"), FadeIn(contents[2]))
        self.at(n.cue(2, "diode"), FadeIn(contents[3]))
        self.at(n.start(3), FadeIn(contents[4]))
        tag = pill("DIFFERENT: the panel is fine", color=OLIVE, size=20).move_to([2.15, -2.7, 0])
        self.at(n.cue(3, "different"), boxes[4][0].animate.set_stroke(OLIVE, width=6), FadeIn(tag, shift=UP * 0.1))
        self.finish()


class Fingerprints(Narrated):
    scene_id = "fingerprints"

    def construct(self):
        n = self.n
        self.header()
        healthy = pvdata.iv(1000.0, 25.0)
        ivx = graph([0, 40, 10], [0, 10, 2], 4.9, 2.4, center=[-3.6, 0.95, 0], y_label="current (A), against voltage (V)")
        pvx = graph([0, 40, 10], [0, 300, 100], 4.9, 2.4, center=[3.6, 0.95, 0], y_label="power (W), against voltage (V)")

        def curves(c, color):
            return VGroup(trace(ivx.ax, c.voltage, c.current, color=color, stroke_width=5),
                          trace(pvx.ax, c.voltage, c.power, color=color, stroke_width=5))

        _, shade = pvdata.fault_iv(FAULT.PARTIAL_SHADING)
        _, soil = pvdata.fault_iv(FAULT.SOILING)
        _, series = pvdata.fault_iv(FAULT.SERIES_RESISTANCE_RISE)
        _, diode = pvdata.fault_iv(FAULT.DIODE_FAILURE)
        _, drift = pvdata.fault_iv(FAULT.SENSOR_DRIFT)
        h_pow = healthy.mpp_power

        def change(c):
            return (c.mpp_power - h_pow) / h_pow * 100

        rows = [
            result_row(-1.25, "Partial shading", f"{h_pow:.1f} → {shade.mpp_power:.1f} W", pct_text(change(shade))),
            result_row(-1.59, "Soiling", f"{h_pow:.1f} → {soil.mpp_power:.1f} W", pct_text(change(soil))),
            result_row(-1.93, "Series resistance rise", f"{h_pow:.1f} → {series.mpp_power:.1f} W", pct_text(change(series))),
            result_row(-2.27, "Diode failure",
                       f"{h_pow:.1f} → {diode.mpp_power:.1f} W  (Voc {diode.voltage[-1]:.1f} V)", pct_text(change(diode))),
            result_row(-2.61, "Sensor drift", f"{h_pow:.1f} → {drift.mpp_power:.1f} W", pct_text(change(drift)), color=FOREST),
        ]
        healthy_g = curves(healthy, FOREST)
        shade_g, soil_g, series_g = curves(shade, OLIVE), curves(soil, OLIVE), curves(series, OLIVE)
        diode_g = curves(diode, OLIVE)
        voc = healthy.voltage[-1]
        voc_line = DashedLine(ivx.ax.c2p(voc, 0), ivx.ax.c2p(voc, 9.2), color=MUTE, stroke_width=3, dash_length=0.12)
        voc_line_p = DashedLine(pvx.ax.c2p(voc, 0), pvx.ax.c2p(voc, 280), color=MUTE, stroke_width=3, dash_length=0.12)
        knee = VGroup(Dot(ivx.ax.c2p(series.mpp_voltage, series.mpp_current), radius=0.1, color=LIME),
                      Dot(pvx.ax.c2p(series.mpp_voltage, series.mpp_power), radius=0.1, color=LIME))
        arrow = Arrow(ivx.ax.c2p(voc, 0.8), ivx.ax.c2p(diode.voltage[-1], 0.8), buff=0, color=OLIVE, stroke_width=6,
                      max_tip_length_to_length_ratio=0.12)

        self.at(n.start(0), FadeIn(ivx), FadeIn(pvx), Create(healthy_g, run_time=1.2), run_time=1.2)
        self.at(n.cue(0, "shading"), FadeIn(rows[0]), Create(shade_g, run_time=1.0))
        self.at(n.start(1), FadeOut(shade_g, run_time=0.5))
        self.at(n.cue(1, "soiling"), FadeIn(rows[1]), Create(soil_g, run_time=1.0))
        self.at(n.start(2), FadeOut(soil_g, run_time=0.5), Create(series_g, run_time=1.0))
        self.at(n.cue(2, "knee"), FadeIn(knee))
        self.at(n.cue(2, "open"), Create(voc_line), Create(voc_line_p), run_time=0.7)
        self.at(n.cue(2, "falls"), FadeIn(rows[2]))
        self.at(n.start(3), FadeOut(series_g), FadeOut(knee), FadeOut(voc_line), FadeOut(voc_line_p), Create(diode_g, run_time=1.0))
        self.at(n.cue(3, "collapses"), FadeIn(rows[3]), GrowArrow(arrow), run_time=1.0)
        self.at(n.start(4), FadeOut(diode_g), FadeOut(arrow), FadeIn(rows[4]))
        self.at(n.cue(4, "exactly"), Indicate(healthy_g))
        self.finish()


class Drift(Narrated):
    scene_id = "drift"

    def construct(self):
        n = self.n
        self.header()
        sun = node(["sun"], 1.6, 1.0).move_to([-5.6, 0.2, 0])
        sensor = node(["irradiance sensor", "reads +15 %"], 3.4, 1.2).move_to([-2.4, 1.5, 0])
        twin = node(["twin"], 1.8, 1.0).move_to([0.8, 1.5, 0])
        out = node(["predicted power", "too high"], 2.8, 1.1, color=MID).move_to([4.9, 1.5, 0])
        plant = node(["plant"], 1.8, 1.0).move_to([0.8, -1.2, 0])
        ok = node(["measured power", "correct"], 2.8, 1.1).move_to([4.9, -1.2, 0])
        a1, a2 = link(sun, sensor), link(sensor, twin)
        a3 = link(twin, out, color=MID)
        a4 = link(sun, plant)
        a5 = link(plant, ok)
        chain = VGroup(sun, sensor, twin, out, plant, ok, a1, a2, a3, a4, a5)

        self.at(n.start(0), FadeIn(sun), Create(a1), FadeIn(sensor), Create(a2), FadeIn(twin),
                FadeIn(plant), Create(a4), FadeIn(ok), Create(a5), run_time=1.2)
        self.at(n.cue(0, "sensor", nth=1), sensor[0].animate.set_stroke(OLIVE, width=7), sensor[1][1].animate.set_color(OLIVE),
                run_time=0.6)
        self.at(n.cue(0, "predicts"), GrowArrow(a3), FadeIn(out), run_time=0.9)
        self.at(n.start(1), FadeOut(chain), run_time=0.6)

        dr = faulty_day(FAULT.SENSOR_DRIFT)
        g = graph([5, 18, 1], [0, 130, 20], 9.0, 3.1, center=[-0.8, 0.0, 0], x_label="time of day (hours)", y_label="power (W)")
        ax = g.ax
        meas = trace(ax, dr.hours, dr.measured, color=INK, stroke_width=5)
        pred = DashedVMobject(trace(ax, dr.hours, dr.predicted, color=MID, stroke_width=5), num_dashes=90)
        daylight_after = (dr.hours >= 11.5) & (dr.predicted >= 5)
        dev_pill = pill(f"{dr.deviation[daylight_after].mean():.1f} %", color=OLIVE, size=26).move_to([5.3, 1.3, 0])
        state = pill("Abnormal", color=OLIVE, size=26).move_to([5.3, 0.1, 0])
        self.at(n.start(1) + 0.7, FadeIn(g), Create(meas, run_time=2.4, rate_func=linear), Create(pred, run_time=2.4, rate_func=linear))
        self.at(n.cue(1, "minus"), FadeIn(dev_pill))
        self.at(n.cue(1, "abnormal"), FadeIn(state))
        self.at(n.start(2), FadeOut(g), FadeOut(dev_pill), FadeOut(state), run_time=0.6)
        callout_box = callout("The panel,\nor the sensor?", tag="ASK", size=28).move_to([0, 0.2, 0])
        self.at(n.start(2) + 0.05, FadeIn(callout_box, shift=UP * 0.2))
        self.at(n.cue(2, "sensor"), Indicate(callout_box))
        self.finish()


class Day(Narrated):
    scene_id = "day"

    def construct(self):
        n = self.n
        self.header()
        healthy = healthy_day()
        fault = faulty_day(FAULT.PARTIAL_SHADING)
        pw = graph([0, 24, 2], [0, 140, 20], 8.6, 2.3, center=[-1.2, 0.85, 0], y_label="power (W)")
        ax = pw.ax
        before = healthy.hours <= 11.0
        after = fault.hours >= 11.0
        meas_0 = trace(ax, healthy.hours[before], healthy.measured[before], color=INK, stroke_width=5)
        pred_0 = DashedVMobject(trace(ax, healthy.hours[before], healthy.predicted[before], color=MID, stroke_width=5), num_dashes=70)
        meas_1 = trace(ax, fault.hours[after], fault.measured[after], color=INK, stroke_width=5)
        pred_1 = DashedVMobject(trace(ax, fault.hours[after], fault.predicted[after], color=MID, stroke_width=5), num_dashes=70)
        marker = DashedLine(ax.c2p(11, 0), ax.c2p(11, 136), color=OLIVE, stroke_width=3, dash_length=0.12)
        marker_label = label("shading injected", size=22, color=OLIVE, weight=BOLD).move_to(ax.c2p(11.3, 128), aligned_edge=LEFT)
        legend = VGroup(pill("measured", color=INK, size=22).move_to(ax.c2p(16.2, 112), aligned_edge=LEFT),
                        pill("predicted", color=MID, size=22).move_to(ax.c2p(16.2, 80), aligned_edge=LEFT))
        normal = pill("Normal", color=MID, size=26).move_to([5.2, 1.6, 0])

        # the deviation strip (below the power plot), from the faulty day; the hours are read off the plot above
        dv = graph([0, 24, 2], [-40, 10, 10], 8.6, 1.5, center=[-1.2, -2.0, 0], y_label="deviation (%)", numbers=True, x_numbers=False)
        dax = dv.ax
        dmask = fault.predicted >= 5
        dev_tr = trace(dax, fault.hours[dmask], fault.deviation[dmask], color=FOREST, stroke_width=4)
        lim5 = DashedLine(dax.c2p(0, -5), dax.c2p(24, -5), color=PALE, stroke_width=3, dash_length=0.15)
        lim10 = DashedLine(dax.c2p(0, -10), dax.c2p(24, -10), color=PALE, stroke_width=3, dash_length=0.15)
        lim_labels = VGroup(label("-5 %", size=18, color=MUTE).next_to(dax.c2p(24, -5), RIGHT, buff=0.15),
                            label("-10 %", size=18, color=MUTE).next_to(dax.c2p(24, -10), RIGHT, buff=0.15))

        self.at(n.start(0), FadeIn(pw), FadeIn(normal), FadeIn(legend), run_time=0.8)
        self.at(n.cue(0, "morning"), Create(meas_0, run_time=3.0, rate_func=linear), Create(pred_0, run_time=3.0, rate_func=linear))
        self.at(n.cue(1, "eleven"), Create(marker), FadeIn(marker_label), run_time=0.6)
        self.at(n.cue(1, "drops"), Create(meas_1, run_time=2.4, rate_func=linear), Create(pred_1, run_time=2.4, rate_func=linear))
        self.at(n.start(2), FadeIn(dv), FadeIn(lim_labels), FadeIn(lim5), FadeIn(lim10), run_time=0.6)
        self.at(n.start(2) + 0.1, Create(dev_tr, run_time=2.0, rate_func=linear))
        self.at(n.cue(2, "warning"), Indicate(lim5, color=LIME))
        self.at(n.cue(2, "abnormal"), Indicate(lim10, color=LIME))

        abnormal = pill("Abnormal", color=OLIVE, size=26).move_to(normal.get_center())
        just_after = (fault.hours >= 11.0) & (fault.hours < 11.5) & (fault.predicted >= 5)
        alarm_value = fault.deviation[just_after].mean()    # the deviation when the alarm is raised, about -31 %
        alarm = card(3.1, 2.0).set_stroke(OLIVE, width=4).move_to([5.0, -0.5, 0])
        alarm_text = VGroup(label("ALARM", size=26, color=OLIVE, weight=BOLD), label("partial shading", size=24, color=INK),
                            label(f"{alarm_value:.0f} %", size=30, color=OLIVE, weight=BOLD)).arrange(DOWN, aligned_edge=LEFT, buff=0.18)
        alarm_text.move_to(alarm).align_to(alarm, LEFT).shift(RIGHT * 0.3)
        self.at(n.cue(3, "abnormal"), Transform(normal, abnormal), run_time=0.6)
        self.at(n.cue(3, "alarm"), FadeIn(alarm, shift=LEFT * 0.5), FadeIn(alarm_text, shift=LEFT * 0.5))
        self.finish()


class Recap(Narrated):
    scene_id = "recap"

    def construct(self):
        n = self.n
        self.header()
        items = VGroup(
            label("plant = twin + mismatch + noise", size=32, color=INK),
            label("five faults: shading, soiling, Rs, diode, sensor drift", size=32, color=INK),
            label("each leaves its own fingerprint", size=32, color=INK),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.55).move_to([0, 0.5, 0])
        ticks = VGroup(*[Dot(items[i].get_left() + LEFT * 0.35, radius=0.09, color=LIME) for i in range(3)])
        self.at(n.cue(0, "plant"), FadeIn(items[0], shift=RIGHT * 0.2), FadeIn(ticks[0]))
        self.at(n.cue(0, "faults"), FadeIn(items[1], shift=RIGHT * 0.2), FadeIn(ticks[1]))
        self.at(n.cue(0, "fingerprint"), FadeIn(items[2], shift=RIGHT * 0.2), FadeIn(ticks[2]))

        sidebar = VGroup(Rectangle(width=0.5, height=0.8, stroke_color=MID, stroke_width=3, fill_color=PALE, fill_opacity=0.6),
                         *[Line(LEFT * 0.15 + UP * (0.22 - 0.22 * k), RIGHT * 0.15 + UP * (0.22 - 0.22 * k), color=MID, stroke_width=3)
                           for k in range(3)])
        next_card = card(8.2, 2.0).move_to([0, -0.3, 0])
        next_title = label("Tutorial 4: using the app", size=30, color=FOREST, weight=BOLD)
        next_group = VGroup(next_card, next_title, sidebar)
        next_title.move_to(next_card.get_center() + RIGHT * 0.45)
        sidebar.move_to(next_card.get_left() + RIGHT * 0.9)
        self.at(n.start(1), FadeOut(items), FadeOut(ticks), run_time=0.6)
        self.at(n.start(1) + 0.7, FadeIn(next_group, shift=UP * 0.2))
        self.finish()
