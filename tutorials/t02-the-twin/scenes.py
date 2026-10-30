"""PV Digital Twin, Tutorial 2: The twin from first principles: scenes.

Every curve and number comes from common/pvdata.py (the app's own engine). The storyboard is script.json.
"""
from dataclasses import replace

import numpy as np

from common import *

IV_CENTER = (-3.0, 0.2)      # the I-V plot (left half of the frame)
PV_CENTER = (3.8, 0.2)       # the P-V plot, beside the I-V plot
MID_Y = -0.05                # circuit: height midway between the two wires
TOP, BOT = 1.0, -1.1         # circuit wires
X_L, X_SRC, X_RSH, X_D, X_OUT = -6.0, -4.9, -3.4, -1.9, 1.2
IRRADIANCES = (1000, 800, 500, 200)
IRRAD_COLOURS = (FOREST, MID, LIGHT, PALE)


def ink(ax):
    """Tick numbers in INK (the default is too faint on the pale background)."""
    for axis in (ax.x_axis, ax.y_axis):
        if hasattr(axis, "numbers"):
            axis.numbers.set_color(INK)
    return ax



# ------------------------------------------------------------------ drawing helpers
def arrow_tip(at, direction, color=LIME, size=0.2):
    """Arrow head at `at`, pointing along `direction`."""
    tip = Triangle(fill_color=color, fill_opacity=1, stroke_width=0).scale(size)
    tip.rotate(np.arctan2(direction[1], direction[0]) - PI / 2)
    return tip.move_to(at)


def wavy_ray(x, y_top, y_bot, amp=0.09, cycles=2.5):
    """A light ray: a wiggly line falling from y_top to y_bot, with a head."""
    pts = [np.array([x + amp * np.sin(2 * PI * cycles * u), y_top + (y_bot - y_top) * u, 0.0])
           for u in np.linspace(0, 1, 80)]
    return VGroup(polyline(pts, color=LIME, stroke_width=5), arrow_tip(np.array([x, y_bot - 0.08, 0.0]), (0, -1)))


def iv_axes(center=IV_CENTER, width=5.6, height=3.8, numbers=True):
    """Voltage 0 to 40 V on x, current 0 to 10 A on y."""
    ax = Axes(x_range=[0, 40, 10], y_range=[0, 10, 2], x_length=width, y_length=height,
              x_axis_config={"include_numbers": True, "font_size": 18, "color": MUTE},
              y_axis_config={"include_numbers": numbers, "font_size": 18, "color": MUTE}, tips=False)
    return ink(ax.move_to([center[0], center[1], 0]))


def p_axes(center=PV_CENTER, width=5.0, height=3.8):
    """Voltage 0 to 40 V on x, power 0 to 300 W on y."""
    ax = Axes(x_range=[0, 40, 10], y_range=[0, 300, 100], x_length=width, y_length=height,
              x_axis_config={"include_numbers": True, "font_size": 18, "color": MUTE},
              y_axis_config={"include_numbers": True, "font_size": 18, "color": MUTE}, tips=False)
    return ink(ax.move_to([center[0], center[1], 0]))


def axis_titles(ax, x_text, y_text, size=20):
    xt = label(x_text, size, INK).move_to([ax.get_center()[0], ax.get_bottom()[1] - 0.42, 0])
    yt = label(y_text, size, INK)
    yt.move_to([ax.get_left()[0] + yt.width / 2, ax.get_top()[1] + 0.22, 0])   # left edge on the axis
    return VGroup(xt, yt)


def legend(entries, x, y, step=0.48):
    """entries: list of (text, colour). Returns one VGroup per entry so each can appear with its curve."""
    out = []
    for k, (text, col) in enumerate(entries):
        line = Line([x, y - step * k, 0], [x + 0.45, y - step * k, 0], color=col, stroke_width=6)
        out.append(VGroup(line, label(text, 20, INK).next_to(line, RIGHT, buff=0.12)))
    return out


def source_symbol(x, y):
    """Current source: a circle with an arrow inside (the arrow shows the photocurrent direction)."""
    circle = Circle(radius=0.36, color=FOREST, stroke_width=4, fill_color=WHITE, fill_opacity=1).move_to([x, y, 0])
    arrow = Arrow([x, y - 0.22, 0], [x, y + 0.22, 0], buff=0, color=FOREST, stroke_width=4,
                  max_tip_length_to_length_ratio=0.45)
    return VGroup(circle, arrow)


def diode_symbol(x, y):
    """Diode: a triangle pointing down the branch, with a bar at its cathode."""
    tri = Polygon([x - 0.2, y + 0.2, 0], [x + 0.2, y + 0.2, 0], [x, y - 0.14, 0],
                  color=FOREST, fill_color=FOREST, fill_opacity=1, stroke_width=2)
    bar = Line([x - 0.2, y - 0.2, 0], [x + 0.2, y - 0.2, 0], color=FOREST, stroke_width=5)
    return VGroup(tri, bar)


def resistor(x, y, vertical=True):
    w, h = (0.26, 0.9) if vertical else (0.9, 0.26)
    return Rectangle(width=w, height=h, color=FOREST, stroke_width=4, fill_color=WHITE,
                     fill_opacity=1).move_to([x, y, 0])


def vwire(x, y_hi, y_lo):
    return Line([x, y_hi, 0], [x, y_lo, 0], color=FOREST, stroke_width=4)


def hwire(x0, x1, y):
    return Line([x0, y, 0], [x1, y, 0], color=FOREST, stroke_width=4)


def iv_curve(ax, c, colour=FOREST, width=5):
    return trace(ax, c.voltage, c.current, color=colour, stroke_width=width)


# ------------------------------------------------------------------ scene 1: light
class Light(Narrated):
    scene_id = "light"

    def construct(self):
        n = self.n
        self.header()

        # beat 0: light falls on a slim cell, electrons drift, a current leaves
        cell = Rectangle(width=3.8, height=0.42, stroke_color=FOREST, stroke_width=4,
                         fill_color=PALE, fill_opacity=1).move_to([-4.2, 0.4, 0])
        cell_lab = label("silicon cell", 22, FOREST).next_to(cell, DOWN, buff=0.2)
        rays = VGroup(*[wavy_ray(x, 2.3, cell.get_top()[1] + 0.06) for x in (-5.4, -4.6, -3.8, -3.0)])
        self.at(n.start(0), FadeIn(cell), FadeIn(cell_lab), FadeIn(rays, shift=DOWN * 0.2), run_time=0.8)

        electrons = VGroup(*[Dot([x, 0.4, 0], radius=0.075, color=FOREST) for x in (-5.4, -4.6, -3.8)])
        t_e, t_c = n.cue(0, "electrons"), n.cue(0, "current")
        self.at(t_e, FadeIn(electrons, lag_ratio=0.3), run_time=0.5)
        self.at(t_e + 0.5, electrons.animate.shift(RIGHT * 1.3), run_time=t_c - t_e - 0.5, rate_func=linear)

        current = Arrow([-2.2, 0.4, 0], [1.1, 0.4, 0], buff=0, color=FOREST, stroke_width=5)
        current_lab = label("current", 22, FOREST).next_to(current, UP, buff=0.15)
        self.at(t_c, GrowArrow(current), FadeIn(current_lab), run_time=0.7)

        # beat 1: the cell is a current source; its size follows the irradiance (slider)
        src = source_symbol(1.6, 0.4)
        src_lab = tex(r"I_{ph}", size=30, color=FOREST).next_to(src, UP, buff=0.15)
        track = Line([3.0, 1.9, 0], [6.0, 1.9, 0], color=MUTE, stroke_width=6)
        handle = Dot([4.5, 1.9, 0], radius=0.14, color=LIME)
        slider_lab = label("irradiance G", 22, FOREST).move_to([4.5, 2.4, 0])
        bar = Rectangle(width=0.7, height=1.2, fill_color=MID, fill_opacity=1, stroke_width=0).move_to([4.2, -0.4, 0])
        bar_lab = tex(r"I_{ph}", size=30, color=FOREST).move_to([4.2, -1.4, 0])
        self.at(n.start(1), FadeIn(src), FadeIn(src_lab), FadeIn(track), FadeIn(handle), FadeIn(slider_lab),
                FadeIn(bar), FadeIn(bar_lab), run_time=0.9)
        self.at(n.cue(1, "twice", nth=1),
                handle.animate.move_to([6.0, 1.9, 0]),
                bar.animate.stretch_to_fit_height(2.4).move_to([4.2, 0.2, 0]),
                run_time=0.9)
        unit = Text("W/m²", font_size=22, color=FOREST, weight=BOLD).move_to([6.0, 1.45, 0])
        self.at(n.cue(1, "irradiance"), FadeIn(unit), run_time=0.5)

        # beat 2: at 1000 W/m2 the photocurrent is 8.9 A
        eq = tex_parts(r"G = 1000\,\text{W/m}^2", r"\rightarrow", r"I_{ph} = 8.9\,\text{A}", size=40, color=INK)
        eq.move_to([1.6, -2.1, 0])
        self.at(n.start(2), FadeIn(eq), run_time=0.7)
        self.at(n.cue(2, "photocurrent"), Create(highlight_box(eq[2])), run_time=0.6)
        self.finish()


# ------------------------------------------------------------------ scene 2: diode
class Diode(Narrated):
    scene_id = "diode"

    def construct(self):
        n = self.n
        self.header()
        p = pvdata.diode_parameters()

        base = VGroup(hwire(X_L, X_OUT, TOP), hwire(X_L, X_OUT, BOT), vwire(X_L, TOP, BOT), vwire(X_OUT, TOP, BOT))
        source = VGroup(vwire(X_SRC, TOP, BOT), source_symbol(X_SRC, MID_Y))
        i_ph = tex(r"I_{ph}", size=30, color=FOREST).move_to([-5.6, MID_Y, 0])

        # beat 0: the current source, then the diode in parallel with it
        self.at(n.start(0), FadeIn(base), FadeIn(source), FadeIn(i_ph), run_time=0.8)
        diode = VGroup(vwire(X_D, TOP, BOT), diode_symbol(X_D, MID_Y))
        self.at(n.cue(0, "diode"), FadeIn(diode), run_time=0.7)
        diode_arrow = Arrow([-1.45, 0.75, 0], [-1.45, -0.6, 0], buff=0, color=FOREST, stroke_width=5)
        i_d_lab = tex(r"I_d", size=30, color=FOREST).move_to([-1.0, 0.1, 0])
        self.at(n.cue(0, "steals"), GrowArrow(diode_arrow), FadeIn(i_d_lab), run_time=0.7)

        # beat 1: the diode current against voltage, from the engine's own curve:
        # I_d = I_ph - I - (V + I Rs) / Rsh
        stc = pvdata.iv(1000, 25)
        v, i = stc.voltage, stc.current
        i_d = np.clip(p.photocurrent_stc_a - i - (v + i * p.series_resistance_ohm) / p.shunt_resistance_ohm, 0, None)
        dax = ink(Axes(x_range=[0, 40, 10], y_range=[0, 10, 2], x_length=3.1, y_length=2.7,
                       x_axis_config={"include_numbers": True, "font_size": 16, "color": MUTE},
                       y_axis_config={"include_numbers": True, "font_size": 16, "color": MUTE}, tips=False)).move_to([5.0, -0.2, 0])
        dax_lab = VGroup(label("volts", 18, INK).move_to([5.0, -1.9, 0]),
                         tex(r"I_d\,(\text{A})", size=26, color=INK).move_to([3.7, 1.95, 0]))
        curve = trace(dax, v, i_d, color=FOREST, stroke_width=5)
        formula = tex(r"I_d = I_0\left(e^{V/(nV_t)}-1\right)", size=22, color=INK).move_to([4.95, 0.95, 0])
        plot = VGroup(dax, dax_lab, curve, formula)
        self.at(n.start(1), FadeIn(dax), FadeIn(dax_lab), run_time=0.7)
        self.at(n.start(1) + 0.7, Create(curve), run_time=5.0, rate_func=linear)
        self.at(n.cue(1, "exponential"), FadeIn(formula), run_time=0.6)

        # beat 2: back to the circuit; the voltage rises; the diode branch takes more of the current
        v_arrow = Arrow([1.6, BOT, 0], [1.6, TOP, 0], buff=0, color=FOREST, stroke_width=5)
        out_arrow = Arrow([0.5, TOP + 0.42, 0], [1.3, TOP + 0.42, 0], buff=0, color=FOREST, stroke_width=8)
        self.at(n.start(2), FadeOut(plot), GrowArrow(v_arrow), FadeIn(out_arrow), run_time=0.7)
        self.at(n.cue(2, "more"),
                diode_arrow.animate.set_stroke(width=9),
                out_arrow.animate.set_stroke(width=2),
                run_time=0.8)

        # beat 3: label the terminals, then add Rs (series) and Rsh (shunt)
        v_lab = tex("V", size=30, color=INK).move_to([1.95, 0.0, 0])
        i_lab = tex("I", size=30, color=INK).move_to([0.9, TOP + 0.8, 0])
        self.at(n.start(3), FadeIn(v_lab), FadeIn(i_lab), run_time=0.6)
        rs = resistor(-0.2, TOP, vertical=False)
        rs_lab = tex(r"R_s", size=30, color=FOREST).move_to([-0.2, TOP + 0.45, 0])
        self.at(n.cue(3, "series"), FadeIn(rs), FadeIn(rs_lab), run_time=0.7)
        rsh = VGroup(vwire(X_RSH, TOP, BOT), resistor(X_RSH, MID_Y, vertical=True))
        rsh_lab = tex(r"R_{sh}", size=30, color=FOREST).move_to([-3.95, 0.45, 0])
        self.at(n.cue(3, "shunt"), FadeIn(rsh), FadeIn(rsh_lab), run_time=0.7)

        # beat 4: the circuit moves left and shrinks; the equation goes on the right
        circuit = VGroup(base, source, i_ph, diode, diode_arrow, i_d_lab, v_arrow, out_arrow, v_lab, i_lab,
                         rs, rs_lab, rsh, rsh_lab)
        self.at(n.start(4), circuit.animate.scale(0.7).move_to([-3.7, 0.95, 0]), run_time=1.0)
        eq1 = tex_parts(r"I =", r"I_{ph}", r"-", r"I_0\left(e^{\frac{V+IR_s}{nN_sV_t}}-1\right)", size=40, color=INK)
        eq1.move_to([2.9, 0.9, 0])
        eq1[1].set_color(FOREST)
        eq1[3].set_color(MID)
        eq2 = tex_parts(r"-", r"\frac{V+IR_s}{R_{sh}}", size=40, color=INK)
        eq2.move_to([2.9, -0.5, 0])
        eq2[1].set_color(OLIVE)
        self.at(n.cue(4, "equation"), Write(eq1), Write(eq2), run_time=1.0)
        self.at(n.cue(4, "equation") + 1.0, Create(highlight_box(eq1[1])), run_time=0.5)
        self.finish()


# ------------------------------------------------------------------ scene 3: I-V curve
class Curve(Narrated):
    scene_id = "curve"

    def construct(self):
        n = self.n
        self.header()
        stc = pvdata.iv(1000, 25)

        # beat 0: the real I-V curve, drawn over the narration
        ax = iv_axes()
        titles = axis_titles(ax, "voltage (V)", "current (A)")
        curve = iv_curve(ax, stc)
        self.at(n.start(0), FadeIn(ax), FadeIn(titles), run_time=0.7)
        self.at(n.start(0) + 0.7, Create(curve), run_time=5.5, rate_func=linear)
        engine = pill("real data from the app", color=MID, size=22).move_to(ax.c2p(21.0, 4.6))
        self.at(n.cue(0, "engine"), FadeIn(engine), run_time=0.5)

        # beat 1: the short circuit and open circuit end points
        isc_dot = Dot(ax.c2p(0, stc.current[0]), radius=0.1, color=LIME)
        isc_lab = tex(r"I_{sc} = 8.9\ \text{A}", size=28, color=INK).next_to(isc_dot, UR, buff=0.15)
        voc_dot = Dot(ax.c2p(stc.voltage[-1], stc.current[-1]), radius=0.1, color=LIME)
        voc_lab = tex(r"V_{oc} = 37.8\ \text{V}", size=28, color=INK).move_to(ax.c2p(28.5, 1.1))
        self.at(n.cue(1, "short"), FadeIn(isc_dot), FadeIn(isc_lab), run_time=0.6)
        self.at(n.cue(1, "open"), FadeIn(voc_dot), FadeIn(voc_lab), run_time=0.6)

        # beat 2: multiply voltage by current: the power curve appears beside it
        pax = p_axes()
        ptitles = axis_titles(pax, "voltage (V)", "power (W)")
        pcurve = trace(pax, stc.voltage, stc.power, color=MID, stroke_width=5)
        t_m = n.cue(2, "multiply")
        self.at(t_m, FadeIn(pax), FadeIn(ptitles), run_time=0.7)
        self.at(t_m + 0.7, Create(pcurve), run_time=3.2, rate_func=linear)

        # beat 3: the maximum power point, on both curves, with its voltage
        mv, mi, mp = stc.mpp_voltage, stc.mpp_current, stc.mpp_power
        pdot = Dot(pax.c2p(mv, mp), radius=0.1, color=LIME)
        idot = Dot(ax.c2p(mv, mi), radius=0.1, color=LIME)
        power_pill = pill(f"{mp:.1f} W", color=FOREST, size=22).next_to(pdot, UP, buff=0.12)
        i_lab = label(f"{mi:.1f} A", 22, FOREST).next_to(idot, DL, buff=0.1)
        self.at(n.cue(3, "maximum"), FadeIn(pdot), FadeIn(idot), FadeIn(power_pill), FadeIn(i_lab), run_time=0.6)
        drop = DashedLine(pax.c2p(mv, mp), pax.c2p(mv, 0), dash_length=0.1, color=FOREST, stroke_width=3)
        v_lab = label(f"{mv:.1f} V", 22, FOREST).move_to(pax.c2p(mv, 0) + LEFT * 0.6 + UP * 0.3)
        self.at(n.cue(3, "thirty"), Create(drop), FadeIn(v_lab), run_time=0.7)
        self.finish()


# ------------------------------------------------------------------ scene 4: the sun
class Sun(Narrated):
    scene_id = "sun"

    def construct(self):
        n = self.n
        self.header()

        # beat 0: the I-V curve at 1000 W/m2, then 800, 500 and 200 one after another
        ax = iv_axes(numbers=False)
        titles = axis_titles(ax, "voltage (V)", "current (A)")
        curves = [iv_curve(ax, pvdata.iv(g, 25), colour=col) for g, col in zip(IRRADIANCES, IRRAD_COLOURS)]
        # the short circuit current of each curve, marked on the current axis
        marks = []
        for g in IRRADIANCES:
            isc = pvdata.iv(g, 25).current[0]
            marks.append(VGroup(Dot(ax.c2p(0, isc), radius=0.08, color=LIME),
                                label(f"{isc:.2f} A", 18, INK).move_to(ax.c2p(4.5, isc + 0.35))))
        keys = legend([(f"{g} W/m²", col) for g, col in zip(IRRADIANCES, IRRAD_COLOURS)], 0.1, 1.5)
        self.at(n.start(0), FadeIn(ax), FadeIn(titles), Create(curves[0]), FadeIn(keys[0]), FadeIn(marks[0]),
                run_time=0.8)
        t_s = n.cue(0, "sunlight")
        for k in (1, 2, 3):
            self.at(t_s + 1.3 * (k - 1), Create(curves[k]), FadeIn(keys[k]), FadeIn(marks[k]), run_time=1.2)
        self.at(n.start(1), FadeOut(ax, titles, *curves, *keys, *marks), run_time=0.7)

        # beat 1: the power curves for the four irradiances, with their peaks; a table fills row by row
        pax = p_axes(center=IV_CENTER)
        ptitles = axis_titles(pax, "voltage (V)", "power (W)")
        pcurves, peaks, rows = [], [], []
        for g, col in zip(IRRADIANCES, IRRAD_COLOURS):
            c = pvdata.iv(g, 25)
            pcurves.append(trace(pax, c.voltage, c.power, color=col, stroke_width=5))
            peaks.append(Dot(pax.c2p(c.mpp_voltage, c.mpp_power), radius=0.1, color=LIME))
        table = tex_table(
            [[r"G\ (\text{W/m}^2)", r"P_{mpp}\ (\text{W})"]] +
            [[str(g), f"{pvdata.iv(g, 25).mpp_power:.1f}"] for g in IRRADIANCES],
            col_w=[2.0, 2.0], row_h=0.62, size=30)
        table.move_to([4.5, -0.2, 0])
        self.at(n.start(1), FadeIn(pax), FadeIn(ptitles), FadeIn(table[0]), FadeIn(table.cells[0]), run_time=0.7)
        self.at(n.start(1) + 0.7, *[Create(c) for c in pcurves], run_time=1.8)
        for row, cue in zip(range(1, 5), [("thousand", 0), ("eight", 0), ("five", 0), ("two", 2)]):
            t = n.cue(1, cue[0], nth=cue[1])
            self.at(t, FadeIn(table.cells[row]), FadeIn(peaks[row - 1]), run_time=0.5)

        # beat 2: the peak powers against irradiance are a straight line
        gax = ink(Axes(x_range=[0, 1000, 200], y_range=[0, 300, 100], x_length=5.4, y_length=3.8,
                       x_axis_config={"include_numbers": True, "font_size": 18, "color": MUTE},
                       y_axis_config={"include_numbers": True, "font_size": 18, "color": MUTE}, tips=False)).move_to([IV_CENTER[0], IV_CENTER[1], 0])
        gtitles = axis_titles(gax, "irradiance (W/m²)", "power (W)")
        pts = [(g, pvdata.iv(g, 25).mpp_power) for g in IRRADIANCES]
        dots = VGroup(*[Dot(gax.c2p(g, pw), radius=0.1, color=LIME) for g, pw in pts])
        slope = sum(g * pw for g, pw in pts) / sum(g * g for g, _ in pts)
        fit = Line(gax.c2p(0, 0), gax.c2p(1000, slope * 1000), color=MID, stroke_width=5)
        callout_box = callout("expected power\ndepends on the sun", tag="IDEA").move_to([3.9, 0.2, 0])
        self.at(n.start(2), FadeOut(pax, ptitles, table, *pcurves, *peaks), run_time=0.6)
        self.at(n.start(2) + 0.6, FadeIn(gax), FadeIn(gtitles), FadeIn(dots, lag_ratio=0.3), run_time=0.8)
        self.at(n.cue(2, "proportion"), Create(fit), FadeIn(callout_box), run_time=1.0)
        self.finish()


# ------------------------------------------------------------------ scene 5: heat
class Heat(Narrated):
    scene_id = "heat"

    def construct(self):
        n = self.n
        self.header()
        temps = (25, 45, 65)
        cols = (FOREST, MID, LIGHT)

        # beat 0: 25 C, then 45 C and 65 C: the curve shrinks sideways
        ax = iv_axes()
        ytitle = label("current (A)", 20, INK)
        ytitle.move_to([ax.get_left()[0] + ytitle.width / 2, ax.get_top()[1] + 0.22, 0])
        xtitle = label("V", 20, INK).move_to(ax.c2p(40, 0) + RIGHT * 0.3)
        curves = [iv_curve(ax, pvdata.iv(1000, t), colour=c) for t, c in zip(temps, cols)]
        keys = legend([(f"{t} °C", c) for t, c in zip(temps, cols)], 0.1, 1.5)
        self.at(n.start(0), FadeIn(ax), FadeIn(ytitle), FadeIn(xtitle), Create(curves[0]), FadeIn(keys[0]),
                run_time=0.8)
        t_h = n.cue(0, "hotter")
        self.at(t_h, Create(curves[1]), FadeIn(keys[1]), run_time=1.0)
        self.at(t_h + 1.0, Create(curves[2]), FadeIn(keys[2]), run_time=1.0)

        # the Voc drop: an arrow along the voltage axis, 37.8 -> 35.4 -> 33.0 V
        y_arrow = ax.c2p(0, 0)[1] - 0.45
        voc_arrow = Arrow([ax.c2p(37.8, 0)[0], y_arrow, 0], [ax.c2p(33.0, 0)[0], y_arrow, 0], buff=0,
                          color=OLIVE, stroke_width=5, max_tip_length_to_length_ratio=0.2)
        voc_lab = label("V oc: 37.8 → 35.4 → 33.0 V", 20, OLIVE, weight=BOLD).move_to(
            [ax.c2p(35.4, 0)[0], y_arrow - 0.42, 0])
        self.at(n.cue(0, "sideways"), GrowArrow(voc_arrow), FadeIn(voc_lab), run_time=0.8)

        # beat 1: the three peak powers as bars that shrink with temperature
        bars, bar_labs = VGroup(), VGroup()
        base_y = ax.c2p(0, 0)[1]
        for k, (t, x, c) in enumerate(zip(temps, (2.9, 4.6, 6.2), cols)):
            pw = pvdata.iv(1000, t).mpp_power
            h = 3.0 * pw / 250.0
            bar = Rectangle(width=0.9, height=h, fill_color=c, fill_opacity=1, stroke_width=0).move_to([x, base_y + h / 2, 0])
            bars.add(bar)
            bar_labs.add(label(f"{pw:.1f} W", 22, INK).next_to(bar, UP, buff=0.12),
                         label(f"{t} °C", 22, INK).move_to([x, base_y - 0.4, 0]))
        t_bars = n.cue(1, "twenty"), n.cue(1, "forty"), n.cue(1, "sixty")
        for k in range(3):
            self.at(t_bars[k], GrowFromEdge(bars[k], DOWN), FadeIn(bar_labs[2 * k:2 * k + 2]), run_time=0.7)

        # beat 2: the temperature coefficients, as two equations
        eq_isc = tex(r"I_{sc}(T) = I_{sc}\left(1 + K_i\,(T-25)\right)", size=32, color=INK).move_to([3.9, 1.3, 0])
        eq_isc_v = tex(r"K_i = +0.05\ \%/^{\circ}\text{C}", size=30, color=FOREST).next_to(eq_isc, DOWN, buff=0.25)
        eq_voc = tex(r"V_{oc}(T) = V_{oc}\left(1 + K_v\,(T-25)\right)", size=32, color=INK).move_to([3.9, -0.5, 0])
        eq_voc_v = tex(r"K_v = -0.32\ \%/^{\circ}\text{C}", size=30, color=FOREST).next_to(eq_voc, DOWN, buff=0.25)
        note = label("voltage loses, current gains a little", 20, OLIVE, weight=BOLD).move_to([3.9, -2.2, 0])
        self.at(n.start(2), FadeOut(*keys, bars, bar_labs), run_time=0.6)
        self.at(n.cue(2, "K", nth=0), FadeIn(eq_isc), FadeIn(eq_isc_v), run_time=0.7)
        self.at(n.cue(2, "K", nth=1), FadeIn(eq_voc), FadeIn(eq_voc_v), run_time=0.7)
        self.at(n.cue(2, "voltage"), FadeIn(note), run_time=0.6)
        self.finish()


# ------------------------------------------------------------------ scene 6: datasheet
class Datasheet(Narrated):
    scene_id = "datasheet"

    def construct(self):
        n = self.n
        self.header()
        mod = pvdata.module()

        # beat 0: the datasheet card, rows revealed in the order spoken
        sheet = card(4.8, 4.6).move_to([0, 0.05, 0])
        title = Text("Datasheet", font_size=30, color=FOREST, weight=BOLD).move_to([0, 1.85, 0])
        spec = [
            (r"I_{sc}", f"{mod.isc_a:.1f}\\ \\text{{A}}", ("short", 0)),
            (r"V_{oc}", f"{mod.voc_v:.1f}\\ \\text{{V}}", ("open", 0)),
            (r"I_{mpp}", f"{mod.impp_a:.1f}\\ \\text{{A}}", ("current", 1)),
            (r"V_{mpp}", f"{mod.vmpp_v:.1f}\\ \\text{{V}}", ("voltage", 1)),
            (r"K_i", "+0.05\\ \\%/^{\\circ}\\text{C}", ("two", 0)),
            (r"K_v", "-0.32\\ \\%/^{\\circ}\\text{C}", ("two", 0)),
            (r"N_s", f"{mod.ns}\\ \\text{{cells}}", ("cells", 0)),
        ]
        rows = []
        for k, (lab, val, _cue) in enumerate(spec):
            y = 1.2 - 0.5 * k
            rows.append(VGroup(tex(lab, size=30, color=FOREST).move_to([-1.6, y, 0]),
                               tex(val, size=30, color=INK).move_to([1.2, y, 0])))
        self.at(n.start(0), FadeIn(sheet), FadeIn(title), run_time=0.6)
        for row, (_lab, _val, (word, nth)) in zip(rows, spec):
            self.at(n.cue(0, word, nth=nth), FadeIn(row), run_time=0.4)

        # beat 1: a wrong curve (series resistance too high), morphed into the true one through the datasheet points
        self.at(n.start(1), FadeOut(sheet, title, *rows), run_time=0.6)
        ax = iv_axes(center=(0.0, 0.2), width=7.6, height=3.9)
        titles = axis_titles(ax, "voltage (V)", "current (A)")
        true_p = pvdata.diode_parameters()
        wrong_p = replace(true_p, series_resistance_ohm=1.0)
        wrong = pvdata.solve_curve(pvdata.module(), 1000.0, 25.0, wrong_p)
        true = pvdata.iv(1000, 25)
        wrong_curve = trace(ax, wrong.voltage, wrong.current, color=OLIVE, stroke_width=5)
        true_curve = trace(ax, true.voltage, true.current, color=FOREST, stroke_width=5)
        dots = VGroup(Dot(ax.c2p(0, true.current[0]), radius=0.11, color=LIME),
                      Dot(ax.c2p(true.mpp_voltage, true.mpp_current), radius=0.11, color=LIME),
                      Dot(ax.c2p(true.voltage[-1], 0), radius=0.11, color=LIME))
        self.at(n.start(1), FadeIn(ax), FadeIn(titles), Create(wrong_curve), FadeIn(dots), run_time=0.8)
        self.at(n.cue(1, "adjusts"), Transform(wrong_curve, true_curve), run_time=1.8)
        self.at(n.cue(1, "passes"), *[Flash(d, color=LIME, flash_radius=0.4) for d in dots], run_time=0.9)

        # beat 2: the three fitted numbers, as pills
        self.at(n.start(2), FadeOut(ax, titles, wrong_curve, dots), run_time=0.6)
        fit = true_p
        p_iph = pill(f"I ph = {fit.photocurrent_stc_a:.2f} A", color=MID, size=30).move_to([0, 1.0, 0])
        p_rs = pill(f"R s = {fit.series_resistance_ohm:.2f} Ω", color=MID, size=30).move_to([0, 0.0, 0])
        p_rsh = pill(f"R sh = {fit.shunt_resistance_ohm:,.0f} Ω".replace(",", " "), color=MID, size=30).move_to([0, -1.0, 0])
        self.at(n.start(2), FadeIn(p_iph), run_time=0.5)
        self.at(n.cue(2, "series"), FadeIn(p_rs), run_time=0.5)
        self.at(n.cue(2, "shunt"), FadeIn(p_rsh), run_time=0.5)

        # beat 3: the twin is a block: G and T in, predicted power out
        self.at(n.start(3), FadeOut(p_iph, p_rs, p_rsh), run_time=0.6)
        block = RoundedRectangle(corner_radius=0.15, width=4.2, height=1.6, stroke_color=FOREST, stroke_width=5,
                                 fill_color=WHITE, fill_opacity=1).move_to([-0.2, 0.3, 0])
        block_txt = VGroup(Text("twin:", font_size=26, color=FOREST, weight=BOLD),
                           Text("single diode model", font_size=26, color=FOREST, weight=BOLD)).arrange(DOWN, buff=0.1).move_to(block)
        twin = VGroup(block, block_txt)
        in_arrow = flow_arrow([-4.0, 0.3, 0], block.get_left())
        out_arrow = flow_arrow(block.get_right(), [4.2, 0.3, 0])
        gt = tex(r"G,\ T", size=36, color=FOREST).next_to(in_arrow, UP, buff=0.15)
        out_lab = Text("predicted\npower", font_size=24, color=FOREST, weight=BOLD).next_to(out_arrow, DOWN, buff=0.2)
        self.at(n.start(3), FadeIn(twin), FadeIn(in_arrow), FadeIn(out_arrow), FadeIn(gt), FadeIn(out_lab), run_time=0.8)
        self.at(n.cue(3, "twin"), Circumscribe(twin, color=LIME), run_time=1.0)
        next_card = card(9.0, 1.0).move_to([0, -2.0, 0])
        next_txt = Text("Tutorial 3: the plant and its faults", font_size=28, color=FOREST, weight=BOLD).move_to(next_card)
        self.at(n.cue(3, "Next"), FadeIn(next_card), FadeIn(next_txt), run_time=0.7)
        self.finish()


# ------------------------------------------------------------------ scene 7: recap
class Recap(Narrated):
    scene_id = "recap"

    def construct(self):
        n = self.n
        self.header()

        # beat 0: the checklist, revealed on the cues
        checklist = card(10.6, 3.6).move_to([0, 0.1, 0])
        lines = [
            Text("light → photocurrent I ph (scales with G)", font_size=30, color=FOREST, weight=BOLD),
            Text("diode + Rs + Rsh → the I-V curve", font_size=30, color=FOREST, weight=BOLD),
            Text("datasheet → fitted parameters", font_size=30, color=FOREST, weight=BOLD),
        ]
        lines = VGroup(*lines).arrange(DOWN, aligned_edge=LEFT, buff=0.5).move_to(checklist)
        self.at(n.start(0), FadeIn(checklist), run_time=0.6)
        for k, word in enumerate(("light", "diode", "datasheet")):
            self.at(n.cue(0, word), FadeIn(lines[k], shift=RIGHT * 0.2), run_time=0.5)

        # beat 1: two thumbnails: the sun changes the height, the temperature changes the width
        self.at(n.start(1), FadeOut(checklist, lines), run_time=0.6)
        sun_ax = small_axes([0, 40], [0, 10], 4.8, 3.2).move_to([-3.6, -0.2, 0])
        heat_ax = small_axes([0, 40], [0, 10], 4.8, 3.2).move_to([3.6, -0.2, 0])
        self.at(n.start(1), FadeIn(sun_ax), FadeIn(heat_ax), run_time=0.6)

        sun_title = label("sunlight", 26, FOREST, weight=BOLD).move_to([-3.6, 1.85, 0])
        sun_curves = [iv_curve(sun_ax, pvdata.iv(1000, 25), colour=FOREST, width=6),
                      iv_curve(sun_ax, pvdata.iv(500, 25), colour=LIGHT, width=6)]
        height_lab = label("height", 24, INK).move_to([-3.6, -2.35, 0])
        self.at(n.cue(1, "sunlight"), FadeIn(sun_title), Create(sun_curves[0]), run_time=0.9)
        self.at(n.cue(1, "sunlight") + 0.9, Create(sun_curves[1]), FadeIn(height_lab), run_time=1.0)

        heat_title = label("temperature", 26, FOREST, weight=BOLD).move_to([3.6, 1.85, 0])
        heat_curves = [iv_curve(heat_ax, pvdata.iv(1000, 25), colour=FOREST, width=6),
                       iv_curve(heat_ax, pvdata.iv(1000, 65), colour=LIGHT, width=6)]
        width_lab = label("width", 24, INK).move_to([3.6, -2.35, 0])
        self.at(n.cue(1, "temperature"), FadeIn(heat_title), Create(heat_curves[0]), run_time=0.9)
        self.at(n.cue(1, "temperature") + 0.9, Create(heat_curves[1]), FadeIn(width_lab), run_time=1.0)
        self.finish()
