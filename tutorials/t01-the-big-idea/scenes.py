"""PV Digital Twin, Tutorial 1: The big idea: scenes (animations cued to the narration in script.json)."""
import numpy as np

from common import *


# ------------------------------------------------------------------ drawings shared by several scenes
def sun(r=0.5):
    """A sun: a LIGHT disc with eight rays, centred on the origin."""
    rays = VGroup(*[Line(UP * r * 1.35, UP * r * 1.8, color=LIGHT, stroke_width=6).rotate(k * PI / 4, about_point=ORIGIN)
                    for k in range(8)])
    return VGroup(rays, Circle(radius=r, stroke_width=0, fill_color=LIGHT, fill_opacity=1))


def panel(w=3.0, h=1.8):
    """A PV panel on a roof slab: MID body, PALE cell lines, MUTE roof."""
    body = Rectangle(width=w, height=h, stroke_color=FOREST, stroke_width=4, fill_color=MID, fill_opacity=1)
    grid = VGroup()
    for k in range(1, 6):
        x = -w / 2 + k * w / 6
        grid.add(Line([x, -h / 2, 0], [x, h / 2, 0], color=PALE, stroke_width=2))
    for k in range(1, 4):
        y = -h / 2 + k * h / 4
        grid.add(Line([-w / 2, y, 0], [w / 2, y, 0], color=PALE, stroke_width=2))
    roof = Rectangle(width=w + 0.6, height=0.28, fill_color=MUTE, fill_opacity=1, stroke_width=0).next_to(body, DOWN, buff=0)
    return VGroup(roof, body, grid)


def dashed_arrow(a, b, color=MID):
    """A dashed arrow from a to b: predicted quantities are drawn as mid green dashes."""
    shaft = DashedVMobject(Line(a, b, color=color, stroke_width=6), num_dashes=8, dashed_ratio=0.6)
    tip = Triangle(fill_color=color, fill_opacity=1, stroke_width=0).scale(0.16)
    tip.rotate(np.arctan2(b[1] - a[1], b[0] - a[0]) - PI / 2).move_to(b)
    return VGroup(shaft, tip)


def tick_mark(center, size=0.45, color=MID):
    """A check mark centred on `center`."""
    c = np.array(center, dtype=float)
    pts = [c + np.array(p) * size for p in [(-0.5, 0.0, 0.0), (-0.15, -0.4, 0.0), (0.6, 0.45, 0.0)]]
    return polyline(pts, color=color, stroke_width=10)


def sun_card(title, cx):
    """A white card with a bold title at its top; `cx` is its centre x."""
    shape = card(6.0, 4.5).move_to([cx, 0.1, 0])
    head = Text(title, font_size=24, color=FOREST, weight=BOLD).move_to(shape.get_top() + DOWN * 0.42)
    return VGroup(shape, head)


def state_pill(label, fill, text_color, border=None, size=30):
    """A state pill: a rounded box with a bold label."""
    t = Text(label, font_size=size, color=text_color, weight=BOLD)
    box = RoundedRectangle(corner_radius=0.2, width=t.width + 0.9, height=t.height + 0.6, fill_color=fill, fill_opacity=1,
                           stroke_color=border or fill, stroke_width=4 if border else 0)
    return VGroup(box, t)


# ------------------------------------------------------------------ scenes
class Hook(Narrated):
    scene_id = "hook"

    def construct(self):
        n = self.n
        self.header()
        scene_a = VGroup(panel(3.0, 1.8).move_to([-3.0, 0.2, 0]), sun(0.5).move_to([-5.6, 1.7, 0]))
        meter = pill("100 W", color=FOREST, size=40).move_to([0.6, 0.2, 0])
        question = Text("?", font_size=170, color=OLIVE, weight=BOLD).move_to([4.5, 0.1, 0])
        self.at(n.start(0), FadeIn(scene_a))
        self.at(n.cue(0, "hundred"), FadeIn(meter, shift=RIGHT * 0.3))
        self.at(n.cue(0, "wrong"), FadeIn(question, shift=UP * 0.2))

        # beat 1: two cards, noon on the left, morning on the right
        cards = VGroup(sun_card("Noon, sun at full strength", -3.55), sun_card("Morning, weak sun", 3.55))
        noon_pill = pill("100 W", color=PALE, text_color=INK, size=30).move_to([-3.55, -1.5, 0])
        noon = VGroup(sun(0.45).move_to([-3.55, 0.9, 0]),
                      Text("A healthy panel\nmakes about 250 W", font_size=24, color=INK).move_to([-3.55, -0.45, 0]),
                      noon_pill, Cross(noon_pill, stroke_color=OLIVE, stroke_width=6))
        morning_pill = pill("100 W", color=PALE, text_color=INK, size=30).move_to([3.55, -1.5, 0])
        morning = VGroup(sun(0.25).move_to([3.55, 0.9, 0]),
                         Text("A healthy panel\nmakes about 100 W", font_size=24, color=INK).move_to([3.55, -0.45, 0]),
                         morning_pill, tick_mark(morning_pill.get_right() + RIGHT * 0.65, size=0.5))
        self.at(n.start(1), FadeOut(scene_a, meter, question), FadeIn(cards))
        self.at(n.cue(1, "noon"), FadeIn(noon))
        self.at(n.cue(1, "morning"), FadeIn(morning))

        # beat 2: measured power, then the expected power and the question between them
        measured = Text("measured power", font_size=40, color=INK, weight=BOLD).move_to([0, 0.3, 0])
        self.at(n.start(2), FadeOut(cards, noon, morning), FadeIn(measured))
        expected = Text("expected power", font_size=40, color=MID, weight=BOLD).move_to([3.6, 0.3, 0])
        equal = Text("equal?", font_size=36, color=OLIVE, weight=BOLD).move_to([0, 0.3, 0])
        self.at(n.cue(2, "should"), measured.animate.move_to([-3.6, 0.3, 0]), FadeIn(expected), FadeIn(equal))
        self.finish()


class Twin(Narrated):
    scene_id = "twin"

    def construct(self):
        n = self.n
        self.header()
        g_in = pill("sunlight G", color=PALE, text_color=INK, size=24).move_to([-4.9, 1.2, 0])
        t_in = pill("temperature T", color=PALE, text_color=INK, size=24).move_to([-4.9, -0.9, 0])
        bus_x = -2.6
        bus = Line([bus_x, 1.2, 0], [bus_x, -0.9, 0], color=MUTE, stroke_width=4)
        feed_g = flow_arrow(g_in.get_right() + RIGHT * 0.05, [bus_x, 1.2, 0], width=4)
        feed_t = flow_arrow(t_in.get_right() + RIGHT * 0.05, [bus_x, -0.9, 0], width=4)
        self.at(n.start(0), FadeIn(g_in), FadeIn(t_in), FadeIn(bus), FadeIn(feed_g), FadeIn(feed_t))

        plant_b = block("real panel", width=3.6, height=1.0, size=24).move_to([0.4, 1.2, 0])
        twin_b = block("mathematical copy", width=3.6, height=1.0, size=24).move_to([0.4, -0.9, 0])
        to_plant = flow_arrow([bus_x, 1.2, 0], plant_b.get_left(), width=4)
        to_twin = flow_arrow([bus_x, -0.9, 0], twin_b.get_left(), width=4)
        self.at(n.cue(0, "copy"), FadeIn(plant_b), FadeIn(twin_b), FadeIn(to_plant), FadeIn(to_twin))

        # beat 1: name the blocks, then the two outputs
        self.at(n.cue(1, "plant"), Transform(plant_b[1], Text("PLANT", font_size=26, color=FOREST, weight=BOLD).move_to(plant_b[1])))
        self.at(n.cue(1, "twin"), Transform(twin_b[1], Text("TWIN", font_size=26, color=FOREST, weight=BOLD).move_to(twin_b[1])))
        out_m = flow_arrow(plant_b.get_right(), [3.4, 1.2, 0], width=4)
        meas = pill("measured power", color=INK, text_color=WHITE, size=24).move_to([4.9, 1.2, 0])
        self.at(n.cue(1, "measured"), FadeIn(out_m), FadeIn(meas))
        out_p = dashed_arrow(twin_b.get_right(), [3.4, -0.9, 0])
        pred = pill("predicted power", color=MID, size=24).move_to([4.9, -0.9, 0])
        self.at(n.cue(1, "predicted"), FadeIn(out_p), FadeIn(pred))

        # beat 2: the plant is simulated (dashed outline), with sensor noise; the real hardware is a faded ghost
        outline = DashedVMobject(SurroundingRectangle(plant_b, buff=0.18, color=MID, stroke_width=4), num_dashes=40)
        tag = pill("simulated", color=MID, size=20).move_to([2.7, 2.15, 0])
        self.at(n.cue(2, "simulated"), FadeIn(outline), FadeIn(tag))
        squiggle = ParametricFunction(lambda s: np.array([2.3 + 0.9 * s, 1.2 + 0.14 * np.sin(s * 2 * PI * 5), 0]),
                                      t_range=[0, 1], color=OLIVE, stroke_width=4)
        self.at(n.cue(2, "noise"), Create(squiggle, run_time=0.6))
        ghost = block("real hardware later", width=3.2, height=0.8, size=20).move_to([4.9, -2.1, 0]).set_opacity(0.3)
        self.at(n.cue(2, "hardware"), FadeIn(ghost))
        self.finish()


class Deviation(Narrated):
    scene_id = "deviation"

    def construct(self):
        n = self.n
        self.header()
        f = tex_parts(r"\text{deviation}\,=\,(", r"P_{\text{measured}}", r"-", r"P_{\text{predicted}}",
                      r")\,/\,", r"P_{\text{predicted}}", r"\times 100\,\%", size=44).move_to([0, 1.5, 0])
        f[3].set_color(FOREST)
        f[5].set_color(FOREST)
        self.at(n.start(0), FadeIn(f[0]))
        self.at(n.cue(0, "measured"), FadeIn(f[1]))
        self.at(n.cue(0, "minus"), FadeIn(f[2]))
        self.at(n.cue(0, "predicted"), FadeIn(f[3]))
        self.at(n.cue(0, "divided"), FadeIn(f[4]))
        self.at(n.cue(0, "predicted", nth=1), FadeIn(f[5]))
        self.at(n.cue(0, "percentage"), FadeIn(f[6]))

        # beat 1: 70 measured against 100 predicted
        s = tex_parts(r"(", r"70", r"-", r"100", r")\,/\,", r"100", r"\times 100\,\%", r"=", r"\mathbf{-30\,\%}",
                      size=50).move_to([0, -0.2, 0])
        s[8].set_color(OLIVE)
        tag_low = pill("plant is low", color=OLIVE, size=22).move_to([0, -1.4, 0])
        self.at(n.start(1), FadeIn(s[0]), FadeIn(s[2]), FadeIn(s[4]), FadeIn(s[6]))
        self.at(n.cue(1, "seventy"), FadeIn(s[1]))
        self.at(n.cue(1, "hundred"), FadeIn(s[3]), FadeIn(s[5]))
        self.at(n.cue(1, "minus"), FadeIn(s[7]), FadeIn(s[8]))
        self.at(n.cue(1, "less"), FadeIn(tag_low))

        # beat 2: 104 measured, so the deviation is plus four percent
        p = tex_parts(r"(104-100)\,/\,100\times 100", r"=", r"\mathbf{+4\,\%}", size=50).move_to([0, -0.2, 0])
        p[2].set_color(FOREST)
        tag_high = pill("plant is high", color=MID, size=22).move_to([0, -1.4, 0])
        self.at(n.start(2), FadeOut(s, tag_low))
        self.at(n.cue(2, "four"), FadeIn(p[0]))
        self.at(n.cue(2, "plus"), FadeIn(p[1]), FadeIn(p[2]), FadeIn(tag_high))

        # beat 3: the size of the deviation on a number line, and the sign
        self.at(n.start(3), FadeOut(f, p, tag_high))
        X = lambda v: v * 0.27
        axis = Line([X(-20), 0.3, 0], [X(20), 0.3, 0], color=MUTE, stroke_width=4)
        ticks = VGroup()
        for v in (-20, -10, 0, 10, 20):
            ticks.add(Line([X(v), 0.3, 0], [X(v), 0.45, 0], color=MUTE, stroke_width=3))
            ticks.add(Text(("%+d %%" % v) if v else "0", font_size=22, color=INK).move_to([X(v), -0.15, 0]))
        dot_plus = Dot([X(4), 0.3, 0], radius=0.11, color=LIME)
        dot_minus = Dot([X(-20), 0.3, 0], radius=0.11, color=LIME)
        lab_plus = Text("+4 %", font_size=26, color=FOREST, weight=BOLD).move_to([X(4), 0.85, 0])
        lab_minus = Text("-30 %, past the scale", font_size=22, color=OLIVE, weight=BOLD).move_to([-3.9, 0.85, 0])
        self.at(n.start(3), FadeIn(axis, ticks), FadeIn(dot_plus, dot_minus), FadeIn(lab_plus, lab_minus))

        # the size of each deviation as a bar from zero (the -30 bar runs off the scale, so it is clipped)
        bar_p = Rectangle(width=X(4), height=0.36, fill_color=MID, fill_opacity=1, stroke_width=0).move_to([X(4) / 2, -1.15, 0])
        bar_n = Rectangle(width=abs(X(-20)), height=0.36, fill_color=OLIVE, fill_opacity=1, stroke_width=0).move_to([abs(X(-20)) / 2, -1.7, 0])
        clip_label = Text("30 %, clipped", font_size=20, color=WHITE, weight=BOLD).move_to(bar_n.get_center())
        abs_label = Text("|deviation|", font_size=24, color=FOREST, weight=BOLD).move_to([-2.6, -1.42, 0])
        self.at(n.cue(3, "size"), FadeIn(bar_p, bar_n), FadeIn(clip_label), FadeIn(abs_label))

        arrow_low = Arrow([-0.5, -2.35, 0], [-3.2, -2.35, 0], buff=0, color=OLIVE, stroke_width=6)
        low = Text("low", font_size=26, color=OLIVE, weight=BOLD).move_to([-3.9, -2.35, 0])
        arrow_high = Arrow([0.5, -2.35, 0], [3.2, -2.35, 0], buff=0, color=MID, stroke_width=6)
        high = Text("high", font_size=26, color=MID, weight=BOLD).move_to([3.9, -2.35, 0])
        self.at(n.cue(3, "sign"), FadeIn(arrow_low, low), FadeIn(arrow_high, high))
        self.finish()


class States(Narrated):
    scene_id = "states"

    def construct(self):
        n = self.n
        self.header()
        pn = state_pill("Normal", MID, WHITE)
        pw = state_pill("Warning", PALE, INK, border=OLIVE)
        pa = state_pill("Abnormal", OLIVE, WHITE)
        row = VGroup(pn.copy().move_to([-4.4, 0.5, 0]), pw.copy().move_to([0, 0.5, 0]), pa.copy().move_to([4.4, 0.5, 0]))
        self.at(n.cue(0, "normal"), FadeIn(row[0]))
        self.at(n.cue(0, "warning"), FadeIn(row[1]))
        self.at(n.cue(0, "abnormal"), FadeIn(row[2]))

        # beat 1: the deviation axis with the limits at 5 and 10 percent
        X = lambda v: v * 0.27
        y0, band_h = -0.2, 1.1
        yc = y0 + band_h / 2
        axis = Line([X(-20), -0.45, 0], [X(20), -0.45, 0], color=MUTE, stroke_width=4)
        ticks = VGroup()
        for v, txt in ((-20, "-20"), (-10, "-10"), (-5, "-5"), (0, "0"), (5, "+5"), (10, "+10"), (20, "+20")):
            ticks.add(Line([X(v), -0.45, 0], [X(v), -0.35, 0], color=MUTE, stroke_width=3))
            ticks.add(Text(txt, font_size=20, color=INK).move_to([X(v), -0.9, 0]))
        axis_caption = Text("deviation (%)", font_size=20, color=INK).move_to([0, -1.4, 0])
        self.at(n.start(1), FadeOut(row), FadeIn(axis, ticks, axis_caption))

        def band(a, b, fill, opacity=1.0):
            return Rectangle(width=abs(X(b) - X(a)), height=band_h, fill_color=fill, fill_opacity=opacity, stroke_width=0).move_to(
                [(X(a) + X(b)) / 2, yc, 0])

        normal = VGroup(band(-5, 5, MID), Text("Normal", font_size=22, color=WHITE, weight=BOLD).move_to([0, yc, 0]))
        edges5 = VGroup(*[Line([X(v), y0, 0], [X(v), y0 + band_h, 0], color=INK, stroke_width=3) for v in (-5, 5)])
        self.at(n.cue(1, "five"), FadeIn(normal), FadeIn(edges5))

        warn = VGroup(band(-10, -5, PALE), band(5, 10, PALE),
                      Text("Warning", font_size=20, color=INK, weight=BOLD).move_to([X(7.5), yc, 0]),
                      Text("Warning", font_size=20, color=INK, weight=BOLD).move_to([X(-7.5), yc, 0]))
        abn = VGroup(band(-20, -10, OLIVE), band(10, 20, OLIVE),
                     Text("Abnormal", font_size=22, color=WHITE, weight=BOLD).move_to([X(15), yc, 0]),
                     Text("Abnormal", font_size=22, color=WHITE, weight=BOLD).move_to([X(-15), yc, 0]))
        edges10 = VGroup(*[Line([X(v), y0, 0], [X(v), y0 + band_h, 0], color=INK, stroke_width=3) for v in (-10, 10)])
        self.at(n.cue(1, "ten"), FadeIn(warn), FadeIn(abn), FadeIn(edges10))
        alarm = pill("alarm", color=OLIVE, size=22).move_to([X(15), -1.75, 0])
        self.at(n.cue(1, "alarm"), FadeIn(alarm))

        # beat 2: three readings, a marker dot on the axis and the matching state lit up
        pn2 = state_pill("Normal", MID, WHITE).move_to([-4.4, 1.7, 0])
        pw2 = state_pill("Warning", PALE, INK, border=OLIVE).move_to([0, 1.7, 0])
        pa2 = state_pill("Abnormal", OLIVE, WHITE).move_to([4.4, 1.7, 0])
        dot = Dot([0, -0.45, 0], radius=0.14, color=LIME)
        self.at(n.start(2), FadeIn(pn2, pw2, pa2), FadeIn(dot))
        self.at(n.cue(2, "four"), dot.animate.move_to([X(4), -0.45, 0]), Circumscribe(pn2, color=LIME))
        self.at(n.cue(2, "seven"), dot.animate.move_to([X(-7), -0.45, 0]), Circumscribe(pw2, color=LIME))
        self.at(n.cue(2, "fifteen"), dot.animate.move_to([X(-15), -0.45, 0]), Circumscribe(pa2, color=LIME))

        # beat 3: the limits are settings, shown as editable fields
        diagram = VGroup(axis, ticks, axis_caption, normal, edges5, warn, abn, edges10, dot, pn2, pw2, pa2, alarm)
        self.at(n.start(3), FadeOut(diagram))
        head = pill("Settings > Limits", color=MID, size=26).move_to([0, 1.4, 0])
        rows = VGroup()
        for text, value in (("Normal up to", "5 %"), ("Warning up to", "10 %")):
            field = VGroup(RoundedRectangle(corner_radius=0.1, width=1.6, height=0.65, fill_color=WHITE, fill_opacity=1,
                                            stroke_color=LIME, stroke_width=4),
                           Text(value, font_size=28, color=FOREST, weight=BOLD))
            rows.add(VGroup(Text(text, font_size=26, color=INK), field).arrange(RIGHT, buff=0.6))
        rows.arrange(DOWN, buff=0.5).move_to([0, -0.3, 0])
        self.at(n.start(3), FadeIn(head, shift=DOWN * 0.2), FadeIn(rows))
        self.finish()


class Night(Narrated):
    scene_id = "night"

    def construct(self):
        n = self.n
        self.header()
        d = pvdata.day()
        ax = small_axes([0, 24, 6], [0, 160, 40], 9.6, 2.8).move_to([0, 0.7, 0])
        hour_labels = VGroup(*[Text(t, font_size=20, color=INK).move_to(ax.c2p(h, 0) + DOWN * 0.3)
                               for h, t in ((0, "0 h"), (6, "6"), (12, "12"), (18, "18"), (24, "24 h"))])
        curve = DashedVMobject(trace(ax, d.hours, d.predicted, color=MID, stroke_width=6), num_dashes=90, dashed_ratio=0.6)
        power_label = Text("predicted power", font_size=22, color=MID, weight=BOLD).move_to([0.0, 1.85, 0])
        self.at(n.start(0), Create(ax), FadeIn(hour_labels), run_time=0.7)
        self.at(n.start(0), Create(curve), FadeIn(power_label), run_time=1.4, rate_func=linear)

        # the dark hours at both ends of the day
        day_hours = d.hours[d.predicted >= 5]
        first, last = day_hours[0], day_hours[-1]
        top = ax.get_center()[1]
        shade_l = Rectangle(width=ax.c2p(first, 0)[0] - ax.c2p(0, 0)[0], height=2.8, fill_color=OLIVE, fill_opacity=0.18,
                            stroke_width=0).move_to([(ax.c2p(0, 0)[0] + ax.c2p(first, 0)[0]) / 2, top, 0])
        shade_r = Rectangle(width=ax.c2p(24, 0)[0] - ax.c2p(last, 0)[0], height=2.8, fill_color=OLIVE, fill_opacity=0.18,
                            stroke_width=0).move_to([(ax.c2p(last, 0)[0] + ax.c2p(24, 0)[0]) / 2, top, 0])
        night_label = VGroup(
            Text("night", font_size=20, color=INK).move_to(shade_l.get_center() + UP * 0.9),
            Text("night", font_size=20, color=INK).move_to(shade_r.get_center() + UP * 0.9))
        self.at(n.cue(0, "night"), FadeIn(shade_l, shade_r), FadeIn(night_label))

        # beat 1: the 5 W floor, and the deviation strip that stays at zero below it
        floor = DashedVMobject(Line(ax.c2p(0, 5), ax.c2p(24, 5), color=LIME, stroke_width=4), num_dashes=30)
        floor_label = Text("5 W", font_size=22, color=FOREST, weight=BOLD).move_to(ax.c2p(24, 5) + RIGHT * 0.45)
        self.at(n.cue(1, "five"), Create(floor), FadeIn(floor_label))

        strip = small_axes([0, 24, 6], [-3, 3, 1], 9.6, 0.9).move_to([0, -1.9, 0])
        strip_curve = trace(strip, d.hours, d.deviation, color=FOREST, stroke_width=4)
        strip_label = Text("deviation", font_size=22, color=INK).move_to([-5.85, -1.9, 0])
        self.at(n.cue(1, "zero"), FadeIn(strip, strip_label), Create(strip_curve), run_time=0.7)

        # beat 2: the trap; the chart gives way to the callout
        chart = VGroup(ax, hour_labels, curve, power_label, shade_l, shade_r, night_label, floor, floor_label,
                       strip, strip_label, strip_curve)
        trap = callout("Inject faults in daylight", tag="TRAP", color=OLIVE, size=30).move_to([0, 0.7, 0])
        self.at(n.start(2), FadeOut(chart), FadeIn(trap))
        self.at(n.cue(2, "sun"), FadeIn(sun(0.5).move_to([0, -1.6, 0])))
        self.finish()


class Recap(Narrated):
    scene_id = "recap"

    def construct(self):
        n = self.n
        self.header()
        lines = [r"\text{plant} = \text{the panel (simulated here)}",
                 r"\text{twin} = \text{the model}",
                 r"\text{deviation} = \frac{\text{measured} - \text{predicted}}{\text{predicted}}",
                 r"\text{state} = \text{normal / warning / abnormal}"]
        rows = [VGroup(Dot(radius=0.1, color=LIME), tex(s, size=40)).arrange(RIGHT, buff=0.3) for s in lines]
        checklist = VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=0.55).move_to([0, 0.2, 0])
        for row, cue_word in zip(rows, ("plant", "twin", "deviation", "state")):
            self.at(n.cue(0, cue_word), FadeIn(row, shift=RIGHT * 0.2))

        # beat 1: the checklist shrinks left; the Tutorial 2 card slides in on the right
        self.at(n.start(1), checklist.animate.scale(0.6).move_to([-3.7, 0.2, 0]))
        next_card = card(5.6, 4.6).move_to([3.6, 0.2, 0])
        head = Text("Tutorial 2: The twin", font_size=26, color=FOREST, weight=BOLD).move_to(next_card.get_top() + DOWN * 0.5)
        c = pvdata.iv(1000, 25)
        icon_ax = small_axes([0, 40, 10], [0, 10, 5], 3.8, 2.4).move_to([3.6, -0.4, 0])
        icon_curve = trace(icon_ax, c.voltage, c.current, color=MID, stroke_width=4)
        icon_label = Text("I-V curve", font_size=20, color=INK).move_to([3.6, -1.9, 0])
        self.at(n.start(1), FadeIn(next_card, head, icon_ax, icon_label, shift=LEFT * 0.6), run_time=1.0)
        self.at(n.start(1), Create(icon_curve), run_time=1.0)
        self.finish()
