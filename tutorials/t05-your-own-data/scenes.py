"""PV Digital Twin, Tutorial 5: Using your own data: scenes (the Manim animation of each scene, cued to the narration in script.json)."""
import numpy as np

from common import *


# ------------------------------------------------------------------ helpers local to this video
def _grid(w, h, cols=3, rows=3):
    """A small table icon: a framed grid with a shaded header row."""
    frame = Rectangle(width=w, height=h, stroke_color=FOREST, stroke_width=4, fill_color=WHITE, fill_opacity=1)
    head = Rectangle(width=w, height=h / rows, stroke_width=0, fill_color=PALE, fill_opacity=0.6).move_to([0, h / 2 - h / rows / 2, 0])
    lines = VGroup()
    for k in range(1, cols):
        x = -w / 2 + w * k / cols
        lines.add(Line([x, -h / 2, 0], [x, h / 2, 0], color=FOREST, stroke_width=3))
    for k in range(1, rows):
        y = -h / 2 + h * k / rows
        lines.add(Line([-w / 2, y, 0], [w / 2, y, 0], color=FOREST, stroke_width=3))
    return VGroup(frame, head, lines)


def _plug():
    """A plug drawn with lines: a body with two prongs on top."""
    body = RoundedRectangle(corner_radius=0.1, width=1.3, height=0.9, stroke_color=FOREST, stroke_width=4,
                            fill_color=WHITE, fill_opacity=1)
    prongs = VGroup(*[Line([x, 0.45, 0], [x, 0.85, 0], color=FOREST, stroke_width=7) for x in (-0.3, 0.3)])
    return VGroup(prongs, body)


def _file_icon(text):
    """A sheet of paper with ruled lines and a file name under it."""
    page = RoundedRectangle(corner_radius=0.08, width=1.6, height=2.0, stroke_color=FOREST, stroke_width=4,
                            fill_color=WHITE, fill_opacity=1)
    ruled = VGroup(*[Line([-0.5, 0.5 - 0.3 * k, 0], [0.5, 0.5 - 0.3 * k, 0], color=PALE, stroke_width=5) for k in range(4)])
    name = Text(text, font_size=20, color=FOREST, weight=BOLD).next_to(page, DOWN, buff=0.15)
    return VGroup(page, ruled, name)


def _panel_icon():
    """A small PV panel (a framed grid of cells) for the simulated plant."""
    return _grid(2.4, 1.4, cols=4, rows=2)


def _box(mob, w, h, color=FOREST):
    """Any mobject inside a white rounded box."""
    rect = RoundedRectangle(corner_radius=0.12, width=w, height=h, stroke_color=color, stroke_width=4,
                            fill_color=WHITE, fill_opacity=1)
    return VGroup(rect, mob.move_to(rect))


def _pt(g, px, py, size):
    """Manim point at pixel (px, py) of the screenshot in group g (shot()), for an image of `size` pixels (W, H)."""
    W, H = size
    img = g.image
    return np.array([img.get_left()[0] + px / W * img.width, img.get_top()[1] - py / H * img.height, 0.0])


def _region(g, x0, y0, x1, y1, size):
    """Lime box round a part of a screenshot, given in pixels of an image of `size` (W, H)."""
    W, H = size
    return shot_region(g, x0 / W, y0 / H, x1 / W, y1 / H, buff=0.03)


def _hide(mob):
    """An overlay that is part of a zoomed picture: invisible until its cue (see _show)."""
    return mob.set_opacity(0)


def _show(mob):
    return mob.animate.set_opacity(1)


def _zoom(pic, centre, target, k):
    """Scale the picture by k about `centre` (a point of the picture) and move that point to `target`."""
    return pic.animate.scale(k, about_point=centre).shift(target - centre)


def _unzoom(pic, centre, target, k):
    """Undo _zoom."""
    return pic.animate.shift(centre - target).scale(1 / k, about_point=centre)


def _runs(mask):
    """Runs of equal values in a boolean array: a list of (value, indices), each run extended by one point on both sides."""
    out, start = [], 0
    for i in range(1, len(mask) + 1):
        if i == len(mask) or mask[i] != mask[start]:
            out.append((bool(mask[start]), list(range(max(0, start - 1), min(len(mask), i + 1)))))
            start = i
    return out


class Why(Narrated):
    scene_id = "why"

    def construct(self):
        n = self.n
        self.header()

        # beat 0: irradiance, temperature and power arrive as pills, then join into a table icon
        p_irr = pill("irradiance (W/m²)", color=MID, size=24).move_to([-4.6, 0.8, 0])
        p_tmp = pill("temperature (°C)", color=MID, size=24).move_to([0.0, 0.8, 0])
        p_pow = pill("actual power (W)", color=MID, size=24).move_to([4.6, 0.8, 0])
        self.at(n.cue(0, "irradiance"), FadeIn(p_irr, shift=UP * 0.2))
        self.at(n.cue(0, "temperature"), FadeIn(p_tmp, shift=UP * 0.2))
        self.at(n.cue(0, "power"), FadeIn(p_pow, shift=UP * 0.2))
        table = _grid(2.6, 1.8).move_to([0, 0.8, 0])
        self.at(n.cue(0, "made"), FadeOut(VGroup(p_irr, p_tmp, p_pow)), FadeIn(table))

        # beat 1: a log file slides into the twin, which outputs a row-by-row comparison
        twin = block("digital twin", width=2.8, height=1.2, size=26).move_to([-1.2, 0.8, 0])
        log = _file_icon("log.xlsx\nor log.csv").move_to([-5.2, 0.8, 0])
        out = pill("row-by-row comparison", color=FOREST, size=24).move_to([3.6, 0.8, 0])
        out_arrow = flow_arrow(twin.get_right(), out.get_left())
        self.at(n.start(1), FadeOut(table), FadeIn(twin))
        self.at(n.cue(1, "logger"), FadeIn(log, shift=RIGHT * 0.3))
        self.at(n.cue(1, "tell"), log.animate.move_to(twin.get_center()).set_opacity(0), run_time=1.0)
        self.at(n.cue(1, "row"), FadeIn(out), GrowArrow(out_arrow))

        # beat 2: two ways in: a file (this tutorial), and a live feed from a device (tutorial 7)
        app = block("the app", width=3.0, height=1.8, size=28).move_to([4.2, 0.8, 0])
        self.at(n.start(2), FadeOut(twin, out, out_arrow), FadeIn(app))
        file_src = _file_icon("file").move_to([-4.6, 1.5, 0])
        file_arrow = flow_arrow([-3.6, 1.5, 0], [2.5, 1.2, 0])
        file_note = label("this tutorial", size=24, color=FOREST, weight=BOLD).next_to(file_arrow, UP, buff=0.15)
        self.at(n.cue(2, "file"), FadeIn(file_src), GrowArrow(file_arrow), FadeIn(file_note))
        dev = block("device", width=2.2, height=1.0, size=26).move_to([-4.6, -1.0, 0])
        live_arrow = DashedLine([-3.4, -1.0, 0], [2.5, 0.4, 0], color=FOREST, stroke_width=5).add_tip()
        live_note = label("live feed: tutorial 7", size=24, color=MID, weight=BOLD).move_to([-0.6, -1.15, 0])
        self.at(n.cue(2, "live"), FadeIn(dev), Create(live_arrow), FadeIn(live_note))
        self.finish()


class Template(Narrated):
    scene_id = "template"

    def construct(self):
        n = self.n
        self.header()
        S18 = (1422, 860)

        # beat 0: the Dataset tab, the TEMPLATE button, then save as Excel or CSV
        s = shot("simple_18_dataset_empty.png", width=9.0).move_to([-2.0, 0.0, 0])
        template_box = _region(s, 500, 119, 618, 159, S18)
        p_xl = pill("Excel", color=MID, size=26).move_to([4.6, 1.0, 0])
        p_csv = pill("CSV", color=MID, size=26).move_to([4.6, -0.2, 0])
        self.at(n.start(0), FadeIn(s))
        self.at(n.cue(0, "template"), FadeIn(template_box))
        self.at(n.cue(0, "Excel"), FadeIn(p_xl, shift=LEFT * 0.3))
        self.at(n.cue(0, "C"), FadeIn(p_csv, shift=LEFT * 0.3))

        # beat 1: the columns of the template, with its five example rows, revealed column by column
        headers = ["timestamp", "irradiance_w_m2", "temperature_c", "voltage_v", "current_a"]
        data = [
            ["2025-01-15T09:00:00", "612.4", "31.8", "29.1", "6.02"],
            ["2025-01-15T09:01:00", "618.9", "31.9", "29.1", "6.08"],
            ["2025-01-15T09:02:00", "625.3", "32.0", "29.0", "6.13"],
            ["2025-01-15T09:03:00", "631.7", "32.2", "29.0", "6.19"],
            ["2025-01-15T09:04:00", "638.0", "32.3", "29.0", "6.25"],
        ]
        widths = [3.1, 2.6, 2.4, 1.9, 1.9]
        cols, x = [], -sum(widths) / 2
        for c, head in enumerate(headers):
            cells = [Text(head, font_size=22, color=FOREST, weight=BOLD)] + [Text(r[c], font_size=22, color=INK) for r in data]
            col = VGroup(*cells).arrange(DOWN, buff=0.22)
            col.move_to([x + widths[c] / 2, 1.9 - col.height / 2, 0])
            x += widths[c]
            cols.append(col)
        rule = Line([-sum(widths) / 2, cols[0][0].get_bottom()[1] - 0.12, 0], [sum(widths) / 2, cols[0][0].get_bottom()[1] - 0.12, 0],
                    color=MID, stroke_width=3)
        self.at(n.start(1), FadeOut(s, template_box, p_xl, p_csv), FadeIn(rule))
        self.at(n.cue(1, "timestamp"), FadeIn(cols[0], shift=UP * 0.1))
        self.at(n.cue(1, "irradiance"), FadeIn(cols[1], shift=UP * 0.1))
        self.at(n.cue(1, "temperature"), FadeIn(cols[2], shift=UP * 0.1))
        self.at(n.cue(1, "voltage"), FadeIn(cols[3], shift=UP * 0.1))
        self.at(n.cue(1, "current"), FadeIn(cols[4], shift=UP * 0.1))

        # beat 2: voltage and current are multiplied to give the power; a power column is the alternative
        volts = SurroundingRectangle(VGroup(cols[3], cols[4]), color=LIME, buff=0.15, corner_radius=0.08, stroke_width=5)
        eq = tex_parts(r"\text{power} = \text{voltage} \times \text{current}", size=46).move_to([-2.2, -1.6, 0])
        alt = pill("or a power_w column", color=MID, size=24).move_to([3.7, -1.6, 0])
        self.at(n.cue(2, "multiplies"), Create(volts), FadeIn(eq))
        self.at(n.cue(2, "power", nth=1), FadeIn(alt, shift=LEFT * 0.2))

        # beat 3: the four rules, then the TRAP callout
        rule_texts = [
            "Times must increase (the step may vary)",
            "No blanks",
            "Irradiance cannot be negative",
            "Delete the example rows; paste your own readings from row 2",
        ]
        rule_cues = ["increase", "blanks", "negative", "delete"]
        rows = []
        for txt in rule_texts:
            tick = polyline([[-0.16, 0.0, 0], [-0.05, -0.14, 0], [0.2, 0.22, 0]], stroke_color=FOREST, stroke_width=7)
            rows.append(VGroup(tick, label(txt, size=26, color=INK)).arrange(RIGHT, buff=0.35))
        rules = VGroup(*rows).arrange(DOWN, buff=0.5, aligned_edge=LEFT).move_to([0, 0.7, 0])
        self.at(n.start(3), FadeOut(VGroup(*cols), rule, volts, eq, alt))
        for row, cue in zip(rows, rule_cues):
            self.at(n.cue(3, cue), FadeIn(row, shift=RIGHT * 0.2))
        trap = callout("Excel dates are fine; .xls is not", tag="TRAP", size=24).move_to([0, -1.9, 0])
        self.at(n.cue(3, "paste"), FadeIn(trap))
        self.finish()


class Metrics(Narrated):
    scene_id = "metrics"

    def construct(self):
        n = self.n
        self.header()

        # beat 0: for every row the twin predicts a power, and the error is estimated minus actual
        row = _box(label("row: G, T, actual P", size=24), 3.6, 1.0).move_to([-4.6, 0.8, 0])
        twin = block("twin", width=2.2, height=1.0, size=26).move_to([0, 0.8, 0])
        est = _box(label("estimated P", size=24, color=MID, weight=BOLD), 2.6, 1.0).move_to([4.6, 0.8, 0])
        a1 = flow_arrow(row.get_right(), twin.get_left())
        a2 = flow_arrow(twin.get_right(), est.get_left())
        err = _box(label("error", size=24, color=OLIVE, weight=BOLD), 2.4, 1.0).move_to([4.6, -1.6, 0])
        a3 = flow_arrow(est.get_bottom(), err.get_top())
        minus = label("− actual P", size=22, color=INK).next_to(a3, RIGHT, buff=0.15)
        flow = VGroup(row, twin, a1, a2, est, a3, minus, err)
        self.at(n.cue(0, "every"), FadeIn(row, shift=UP * 0.2))
        self.at(n.cue(0, "predicts"), FadeIn(twin), GrowArrow(a1), FadeIn(est), GrowArrow(a2))
        self.at(n.cue(0, "compares"), GrowArrow(a3), FadeIn(minus), FadeIn(err))

        # beat 1: three rows as a table; actual powers first, then the twin's estimates and the errors
        tbl = tex_table([
            [r"\text{actual } P\,(\text{W})", r"\text{estimated } P\,(\text{W})", r"\text{error}\,(\text{W})"],
            ["80", "82", "+2"],
            ["78", "80", "+2"],
            ["75", "90", "+15"],
        ], col_w=3.1, row_h=0.5, size=36)
        tbl.move_to([0, 1.6, 0])
        for r in (1, 2, 3):
            tbl.cells[r][1].set_color(MID)
            tbl.cells[r][2].set_color(OLIVE)
        defn = tex_parts(r"\text{error} = \text{estimated} - \text{actual}", size=36).move_to([0, -0.3, 0])
        self.at(n.start(1), FadeOut(flow), FadeIn(tbl[0]), FadeIn(tbl.cells[0]))
        self.at(n.cue(1, "eighty"), FadeIn(tbl.cells[1][0]))
        self.at(n.cue(1, "seventy"), FadeIn(tbl.cells[2][0]))
        self.at(n.cue(1, "seventy", nth=1), FadeIn(tbl.cells[3][0]))
        self.at(n.cue(1, "estimates"), FadeIn(defn))
        self.at(n.cue(1, "eighty", nth=1), FadeIn(tbl.cells[1][1]), FadeIn(tbl.cells[1][2]))
        self.at(n.cue(1, "eighty", nth=2), FadeIn(tbl.cells[2][1]), FadeIn(tbl.cells[2][2]))
        self.at(n.cue(1, "ninety"), FadeIn(tbl.cells[3][1]), FadeIn(tbl.cells[3][2]))

        # beat 2: MAE = (|2| + |2| + |15|) / 3 = 6.33 W, written in steps
        self.at(n.start(2), FadeOut(defn))
        mae = tex_parts(r"\text{MAE} = \frac{|2| + |2| + |15|}{3}", r"= 6.33\ \text{W}", size=50).move_to([0, -1.2, 0])
        self.at(n.cue(2, "averages"), FadeIn(mae[0]))
        self.at(n.cue(2, "six"), FadeIn(mae[1]))

        # beat 3: RMSE (with the note on the big miss) and MAPE
        self.at(n.start(3), FadeOut(mae))
        rmse = tex_parts(r"\text{RMSE} = \sqrt{\frac{4 + 4 + 225}{3}}", r"= 8.81\ \text{W}", size=44).move_to([-1.2, -0.9, 0])
        big_note = label("the big miss (15)\ndominates", size=22, color=OLIVE, weight=BOLD).next_to(rmse, RIGHT, buff=0.3)
        mape = tex_parts(r"\text{MAPE} = \frac{2.50\% + 2.56\% + 20.00\%}{3}", r"= 8.35\%", size=44).move_to([0, -2.2, 0])
        self.at(n.cue(3, "squares"), FadeIn(rmse))
        self.at(n.cue(3, "big"), FadeIn(big_note))
        self.at(n.cue(3, "percentage"), FadeIn(mape))

        # beat 4: MBE keeps the sign, so positive means the plant under-produces
        self.at(n.start(4), FadeOut(rmse, big_note, mape))
        mbe = tex_parts(r"\text{MBE} = \frac{2 + 2 + 15}{3}", r"= +6.33\ \text{W}", size=50).move_to([0, -0.3, 0])
        read_it = callout("positive: twin over-predicts,\nplant under-produces", tag="READ IT", size=20).move_to([0, -2.05, 0])
        self.at(n.cue(4, "sign"), FadeIn(mbe))
        self.at(n.cue(4, "positive"), FadeIn(read_it))

        # beat 5: rows where the twin predicts under 5 W are ignored, shown on a simulated day
        self.at(n.start(5), FadeOut(tbl, mbe, read_it))
        d = pvdata.day()
        ax = small_axes([0, 24, 6], [0, 120, 40], width=9.6, height=3.3).move_to([0, -0.5, 0])
        pts = [ax.c2p(h, p) for h, p in zip(d.hours, d.predicted)]
        day_parts, night_parts = VGroup(), VGroup()
        for is_day, idx in _runs(d.predicted >= 5):
            if len(idx) < 2:
                continue
            seg = polyline([pts[i] for i in idx])
            dashed = DashedVMobject(seg, num_dashes=max(8, len(idx) // 6))
            dashed.set_color(MID).set_stroke(width=5)
            (day_parts if is_day else night_parts).add(dashed)
        hour_ticks = VGroup(*[label(str(h), size=20).next_to(ax.c2p(h, 0), DOWN, buff=0.12) for h in (0, 6, 12, 18, 24)])
        power_ticks = VGroup(*[label(str(v), size=20).next_to(ax.c2p(0, v), LEFT, buff=0.15) for v in (0, 40, 80, 120)])
        hour_label = label("hour of day", size=22).move_to(ax.c2p(12, 0) + DOWN * 0.55)
        power_label = label("power (W)", size=22).next_to(ax.c2p(0, 120), UP, buff=0.15, aligned_edge=LEFT)
        threshold = DashedLine(ax.c2p(0, 5), ax.c2p(24, 5), color=FOREST, stroke_width=3, dash_length=0.12)
        threshold_label = label("5 W", size=22, color=FOREST, weight=BOLD).next_to(ax.c2p(24, 5), RIGHT, buff=0.12)
        night_label = label("night: ignored", size=22, color=INK).move_to(ax.c2p(3.5, 30))
        self.at(n.start(5), FadeIn(ax), FadeIn(hour_ticks), FadeIn(power_ticks), FadeIn(hour_label), FadeIn(power_label),
                FadeIn(day_parts), FadeIn(night_parts))
        self.at(n.cue(5, "ignored"), night_parts.animate.set_color(MUTE), FadeIn(threshold), FadeIn(threshold_label),
                FadeIn(night_label))
        self.finish()


class Read(Narrated):
    scene_id = "read"

    def construct(self):
        n = self.n
        self.header()
        S19 = (1422, 860)

        # the screenshot, with its overlays as children so that the zoom on the deviation chart carries them along
        s = shot("simple_19_dataset_results.png", width=9.2).move_to([-1.9, 0.0, 0])
        pic = Group(s)
        diag = DashedLine(_pt(s, 932, 788, S19), _pt(s, 1346, 616, S19), color=FOREST, stroke_width=4, dash_length=0.1)
        healthy = label("healthy", size=22, color=FOREST, weight=BOLD).move_to(_pt(s, 1262, 738, S19))
        shaded = label("shaded", size=22, color=OLIVE, weight=BOLD).move_to(_pt(s, 1000, 660, S19))
        marker = Line(_pt(s, 546, 585, S19), _pt(s, 546, 790, S19), color=OLIVE, stroke_width=4)
        marker_label = label("11:00", size=22, color=OLIVE, weight=BOLD).move_to(_pt(s, 600, 602, S19))
        drop = label("−30 %", size=22, color=OLIVE, weight=BOLD).move_to(_pt(s, 715, 705, S19))
        for overlay in (diag, healthy, shaded, marker, marker_label, drop):
            _hide(overlay)
            pic.add(overlay)
        centre = _pt(s, 533, 700, S19)          # the deviation chart
        target = np.array([-2.0, 0.0, 0.0])
        k = 1.5

        box_size = [
            _region(s, 259, 173, 1381, 271, S19),   # the dataset
            _region(s, 259, 297, 1381, 395, S19),   # the accuracy figures
            _region(s, 259, 421, 1381, 519, S19),   # the deviation and state figures
        ]
        box_left = _region(s, 259, 560, 807, 832, S19)     # lower left: power deviation
        box_right = _region(s, 833, 560, 1381, 832, S19)   # lower right: estimated against actual

        # beat 0: the three groups of figures in turn
        self.at(n.start(0), FadeIn(pic))
        self.at(n.cue(0, "size"), FadeIn(box_size[0]))
        self.at(n.cue(0, "accuracy"), FadeOut(box_size[0]), FadeIn(box_size[1]))
        self.at(n.cue(0, "state"), FadeOut(box_size[1]), FadeIn(box_size[2]))

        # beat 1: the two charts; the dashed diagonal is where a healthy panel lies
        self.at(n.cue(1, "left"), FadeOut(box_size[2]), FadeIn(box_left))
        self.at(n.cue(1, "right"), FadeOut(box_left), FadeIn(box_right))
        self.at(n.cue(1, "healthy"), FadeOut(box_right), _show(diag), _show(healthy))

        # beat 2: zoom on the deviation chart at 11:00, the drop to about -30 %, then back out for the abnormal count
        self.at(n.cue(2, "shading"), _show(shaded))
        self.at(n.cue(2, "eleven"), _zoom(pic, centre, target, k), run_time=0.9)
        self.at(n.cue(2, "eleven") + 0.9, _show(marker), _show(marker_label))   # after the zoom, so the two never animate together
        self.at(n.cue(2, "thirty"), _show(drop))
        self.at(n.cue(2, "nearly"), _unzoom(pic, centre, target, k), run_time=0.9)
        abnormal = pill("Abnormal 48.1 %", color=OLIVE, size=24).move_to([4.7, 0.6, 0])
        self.at(n.cue(2, "abnormal"), FadeIn(abnormal))
        self.finish()


class Replay(Narrated):
    scene_id = "replay"

    def construct(self):
        n = self.n
        self.header()
        S21 = (1422, 860)

        s = shot("simple_21_dashboard_replay.png", width=9.2).move_to([-1.9, 0.0, 0])
        pause_box = _region(s, 312, 117, 364, 143, S21)
        chart_box = _region(s, 267, 307, 1068, 825, S21)
        chip_box = _region(s, 1048, 38, 1246, 62, S21)
        pause_icon = VGroup(
            Circle(radius=0.45, fill_color=FOREST, fill_opacity=1, stroke_width=0),
            Rectangle(width=0.14, height=0.42, fill_color=WHITE, fill_opacity=1, stroke_width=0).shift(LEFT * 0.12),
            Rectangle(width=0.14, height=0.42, fill_color=WHITE, fill_opacity=1, stroke_width=0).shift(RIGHT * 0.12),
        ).move_to([5.2, 1.4, 0])
        pause_word = label("paused", size=22, color=INK).next_to(pause_icon, DOWN, buff=0.2)

        # beat 0: Replay pauses the live run; the dashboard shows the dataset
        self.at(n.start(0), FadeIn(s))
        self.at(n.cue(0, "pauses"), FadeIn(pause_box), FadeIn(pause_icon), FadeIn(pause_word))
        self.at(n.cue(0, "Dashboard", nth=1), FadeOut(pause_box), FadeIn(chart_box))

        # beat 1: the source chip at the top right
        self.at(n.start(1), FadeOut(pause_icon, pause_word))
        self.at(n.cue(1, "chip"), FadeOut(chart_box), FadeIn(chip_box))

        # beat 2: export the analysis, and apply and start brings the simulated plant back
        p_exp = pill("Export analysis CSV", color=MID, size=26).move_to([-3.0, 1.2, 0])
        f_csv = _file_icon("analysis.csv").move_to([3.6, 1.2, 0])
        a_exp = flow_arrow(p_exp.get_right(), f_csv.get_left())
        p_apply = pill("Apply and start", color=FOREST, size=26).move_to([-3.0, -1.2, 0])
        plant = _panel_icon().move_to([3.6, -1.2, 0])
        plant_word = label("simulated plant", size=22, color=INK).next_to(plant, DOWN, buff=0.15)
        a_apply = flow_arrow(p_apply.get_right(), plant.get_left())
        self.at(n.cue(2, "export"), FadeOut(s, chip_box), FadeIn(p_exp), GrowArrow(a_exp), FadeIn(f_csv))
        self.at(n.cue(2, "apply"), FadeIn(p_apply), GrowArrow(a_apply), FadeIn(plant), FadeIn(plant_word))
        self.finish()


class Settings(Narrated):
    scene_id = "settings"

    def construct(self):
        n = self.n
        self.header()

        # beat 0: the Profile section: the weather file loads from CSV or Excel, and has a template
        s0 = shot("simple_22_settings_profile.png", width=8.8)
        load_box = _region(s0, 493, 263, 1092, 296, (1400, 900))
        template_box = _region(s0, 1099, 263, 1196, 296, (1400, 900))
        self.at(n.start(0), FadeIn(s0))
        self.at(n.cue(0, "weather", nth=1), FadeIn(load_box))
        self.at(n.cue(0, "template"), FadeOut(load_box), FadeIn(template_box))

        # beat 1: the Module section: the datasheet, and its template
        s1 = shot("simple_23_settings_module.png", width=8.8)
        datasheet_box = _region(s1, 493, 442, 723, 475, (1400, 900))
        datasheet_template_box = _region(s1, 730, 442, 959, 475, (1400, 900))
        self.at(n.start(1), FadeOut(s0, template_box), FadeIn(s1))
        self.at(n.cue(1, "module"), FadeIn(datasheet_box))
        self.at(n.cue(1, "template"), FadeOut(datasheet_box), FadeIn(datasheet_template_box))

        # beat 2: nothing changes until apply and start
        s2 = shot("simple_16_settings.png", width=9.2)
        apply_box = _region(s2, 1255, 795, 1398, 835, (1422, 860))
        self.at(n.start(2), FadeOut(s1, datasheet_template_box), FadeIn(s2))
        self.at(n.cue(2, "apply"), FadeIn(apply_box))
        self.finish()


class Recap(Narrated):
    scene_id = "recap"

    def construct(self):
        n = self.n
        self.header()

        # beat 0: the checklist, one item per cue
        texts = [
            "A dataset: irradiance, temperature and power",
            "The template: the columns to fill in",
            "Scores: how well the twin matches your panel",
        ]
        rows = []
        for txt in texts:
            box = Square(side_length=0.45, stroke_color=FOREST, stroke_width=4, fill_color=WHITE, fill_opacity=1)
            text = label(txt, size=30, color=INK)
            text.next_to(box, RIGHT, buff=0.35)
            tick = polyline([[-0.14, 0.0, 0], [-0.04, -0.13, 0], [0.17, 0.17, 0]], stroke_color=FOREST, stroke_width=7)
            tick.move_to(box.get_center())
            rows.append(VGroup(box, tick, text))
        checklist = VGroup(*rows).arrange(DOWN, buff=0.6, aligned_edge=LEFT).move_to(ORIGIN)
        self.at(n.cue(0, "dataset"), FadeIn(rows[0], shift=RIGHT * 0.2))
        self.at(n.cue(0, "template"), FadeIn(rows[1], shift=RIGHT * 0.2))
        self.at(n.cue(0, "scores"), FadeIn(rows[2], shift=RIGHT * 0.2))

        # beat 1: the next tutorial
        next_card = card(8.6, 2.6)
        next_text = Text("Tutorial 6: limits and trust", font_size=40, color=FOREST, weight=BOLD).move_to(next_card)
        self.at(n.start(1), FadeOut(checklist), FadeIn(VGroup(next_card, next_text)))
        self.finish()
