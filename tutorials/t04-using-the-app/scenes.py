"""PV Digital Twin, Tutorial 4: Using the app: scenes (Manim animation cued to the narration in script.json).

Screenshot fractions (fx, fy) are measured on the PNGs in docs/screenshots: (0, 0) is the top left of the image.
"""
import numpy as np

from common import *


def fp(g, fx, fy):
    """Point at fraction (fx, fy) of a screenshot Group made by shot()."""
    img = g.image
    return np.array([img.get_left()[0] + fx * img.width, img.get_top()[1] - fy * img.height, 0])


def fbox(g, fx0, fy0, fx1, fy1):
    """Lime box round a part of a screenshot, in fractions."""
    return shot_region(g, fx0, fy0, fx1, fy1)


def tag(text, color=FOREST, size=22):
    return pill(text, color=color, size=size)


def dash_note(text, size=24):
    return Text(text, font_size=size, color=INK)


class Open(Narrated):
    scene_id = "open"

    def construct(self):
        n = self.n
        self.header()
        g = shot("simple_01b_dashboard_idle_8pages.png", width=8.0)
        self.at(n.start(0), FadeIn(g))
        win = fbox(g, 0.0, 0.0, 1.0, 1.0)
        self.at(n.cue(0, "one"), Create(win), run_time=0.6)
        self.at(n.cue(0, "one") + 1.5, FadeOut(win), run_time=0.4)

        # beat 1: number the eight pages beside the sidebar (rows measured on the 1400 x 994 image), flash the Dashboard
        rows = [0.149, 0.199, 0.248, 0.298, 0.347, 0.396, 0.446, 0.495]
        def badge(k):
            # rows are only about 0.28 units apart, so the numbers are small round badges, not pills
            return VGroup(Circle(radius=0.125, fill_color=MID, fill_opacity=1, stroke_width=0),
                          Text(str(k), font_size=15, color=WHITE, weight=BOLD))
        nums = VGroup(*[badge(i + 1).move_to(fp(g, 0, y) + LEFT * 0.3) for i, y in enumerate(rows)])
        self.at(n.cue(1, "eight"), LaggedStart(*[FadeIn(p) for p in nums], lag_ratio=0.15))
        dash = fbox(g, 0.01, 0.125, 0.155, 0.172)
        self.at(n.cue(1, "Dashboard"), Circumscribe(dash, color=LIME, run_time=1.0))

        # beat 2: arrows from the sidebar into the page: one run
        arrows, labels = VGroup(), VGroup()
        for fy in (0.199, 0.298, 0.396):
            a, b = fp(g, 0.165, fy), fp(g, 0.40, fy + 0.20)
            arrows.add(Arrow(a, b, buff=0.05, color=FOREST, stroke_width=5, max_tip_length_to_length_ratio=0.15))
            labels.add(tag("same run", size=20).move_to(b + RIGHT * 0.95))
        self.at(n.cue(2, "same"), LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.25), FadeIn(labels))
        self.finish()


class Controls(Narrated):
    scene_id = "controls"

    def construct(self):
        n = self.n
        self.header()
        g = shot("simple_03_toolbar.png", width=12.5).move_to([0, 1.2, 0])
        self.at(n.start(0), FadeIn(g))
        # beat 0: Start, Pause, Reset (measured from the toolbar screenshot)
        names = [("Start", 0.0, 0.05, "Plays the run from the beginning"),
                 ("Pause", 0.05, 0.10, "Holds the run where it is"),
                 ("Reset", 0.10, 0.155, "Clears the run, faults and alarms")]
        notes = VGroup()
        for k, (word, x0, x1, text) in enumerate(names):
            box = fbox(g, x0, 0.05, x1, 0.95)
            self.at(n.cue(0, word.lower()), Create(box), run_time=0.5)
            note = VGroup(tag(word, size=22), label(text, size=24, color=INK)).arrange(RIGHT, buff=0.3)
            note.move_to([-4.4 + note.width / 2, 0.1 - 0.95 * k, 0])
            notes.add(note)
            self.at(n.cue(0, word.lower()) + 0.6, FadeIn(note), run_time=0.4)
            self.at(n.cue(0, word.lower()) + 1.4, FadeOut(box), run_time=0.3)
        # beat 1: speed box and the 600x tip
        self.at(n.start(1), FadeOut(notes), run_time=0.4)
        speed = fbox(g, 0.165, 0.05, 0.235, 0.95)
        self.at(n.cue(1, "speed"), Create(speed), run_time=0.5)
        tip = callout("600x", tag="TIP", color=OLIVE, size=28, width=3.2).move_to([-2.2, -1.0, 0])
        self.at(n.cue(1, "six"), FadeIn(tip), run_time=0.5)
        self.at(n.cue(1, "six") + 2.5, FadeOut(speed), FadeOut(tip), run_time=0.4)
        # beat 2: clock
        clock = fbox(g, 0.235, 0.05, 0.335, 0.95)
        self.at(n.cue(2, "clock"), Create(clock), run_time=0.5)
        self.at(n.cue(2, "clock") + 2.5, FadeOut(clock), run_time=0.4)
        # beat 3: five fault buttons, numbered; the dark one is switched on
        faults = [(0.515, 0.600), (0.612, 0.67), (0.678, 0.75), (0.757, 0.84), (0.852, 0.925)]
        marks = VGroup(*[tag(str(i + 1), size=20).move_to(fp(g, (a + b) / 2, 0) + UP * 0.65)
                         for i, (a, b) in enumerate(faults)])
        self.at(n.cue(3, "five"), LaggedStart(*[FadeIn(m) for m in marks], lag_ratio=0.12))
        dark = fbox(g, 0.515, 0.05, 0.60, 0.95)
        self.at(n.cue(3, "dark"), Create(dark), run_time=0.5)
        self.finish()


class Readings(Narrated):
    scene_id = "readings"

    def construct(self):
        n = self.n
        self.header()
        cards = shot("simple_04_readings.png", width=12.5).move_to([0, 1.2, 0])
        self.at(n.start(0), FadeIn(cards))
        spans = {"voltage": (0.0, 0.156), "current": (0.17, 0.335), "measured": (0.348, 0.489),
                 "predicted": (0.501, 0.66), "irradiance": (0.672, 0.831), "temperature": (0.845, 1.0)}
        for word, (a, b) in spans.items():
            box = fbox(cards, a, 0.0, b, 1.0)
            self.at(n.cue(0, word), Create(box), run_time=0.4)
            self.play(FadeOut(box), run_time=0.2)
        note = tag("dashes before a run", color=OLIVE, size=22).move_to([0, -0.5, 0])
        self.at(n.cue(0, "dashes"), FadeIn(note), run_time=0.5)
        self.at(n.start(1), FadeOut(cards), FadeOut(note), run_time=0.5)

        # beat 1: the chart, measured in black, predicted in green dashes, a dashed fault line
        chart = shot("simple_06_dashboard_fault.png", width=9.0).move_to([-0.5, -0.1, 0])
        self.at(n.start(1), FadeIn(chart), run_time=0.6)
        card = fbox(chart, 0.17, 0.34, 0.76, 0.975)
        self.at(n.cue(1, "black") - 0.4, Create(card), run_time=0.4)
        meas = tag("measured", color=INK, size=22).move_to([5.3, 0.75, 0])
        pred = tag("predicted", color=FOREST, size=22).move_to([5.3, -0.25, 0])
        a_meas = Arrow(meas.get_left(), fp(chart, 0.215, 0.375), buff=0.05, color=FOREST, stroke_width=4)
        a_pred = Arrow(pred.get_left(), fp(chart, 0.215, 0.403), buff=0.05, color=FOREST, stroke_width=4)
        self.at(n.cue(1, "black"), FadeIn(meas), Create(a_meas), run_time=0.6)
        self.at(n.cue(1, "green"), FadeIn(pred), Create(a_pred), run_time=0.6)
        fault_pill = tag("fault injected", color=OLIVE, size=22).move_to([5.3, -1.6, 0])
        a_fault = Arrow(fault_pill.get_left(), fp(chart, 0.7286, 0.55), buff=0.05, color=OLIVE, stroke_width=4)
        self.at(n.cue(1, "vertical"), FadeIn(fault_pill), Create(a_fault), run_time=0.6)

        # beat 2: zoom and pan with the wheel, export on hover
        self.at(n.start(2), FadeOut(chart), FadeOut(card), FadeOut(meas), FadeOut(pred), FadeOut(fault_pill),
                FadeOut(a_meas), FadeOut(a_pred), FadeOut(a_fault), run_time=0.5)
        chart2 = shot("simple_06_dashboard_fault.png", width=9.0).move_to([-0.5, -0.1, 0])
        self.at(n.start(2), FadeIn(chart2), run_time=0.5)
        centre = fp(chart2, 0.5, 0.6)
        lens = VGroup(Circle(radius=0.32, stroke_color=FOREST, stroke_width=6, fill_opacity=0),
                      Line(UR * 0.23, UR * 0.6, color=FOREST, stroke_width=8)).move_to(centre)
        self.at(n.cue(2, "wheel"), FadeIn(lens), run_time=0.5)
        self.at(n.cue(2, "export"), FadeIn(tag("Export", size=20).move_to(fp(chart2, 0.70, 0.355))), run_time=0.5)
        self.finish()


class Deviation(Narrated):
    scene_id = "deviation"

    def construct(self):
        n = self.n
        self.header()
        healthy = shot("simple_05_deviation_card.png", width=2.46).move_to([-5.0, -0.45, 0])
        fault = shot("simple_07_deviation_card_fault.png", width=2.46).move_to([5.0, -0.45, 0])
        self.at(n.start(0), FadeIn(healthy), FadeIn(fault))
        h_lab = label("healthy", size=24, color=MID, weight=BOLD).move_to([-5.0, 2.45, 0])
        f_lab = label("fault on", size=24, color=OLIVE, weight=BOLD).move_to([5.0, 2.45, 0])
        self.at(n.start(0), FadeIn(h_lab), FadeIn(f_lab))
        big = fbox(fault, 0.05, 0.065, 0.5, 0.15)
        self.at(n.cue(0, "large"), Create(big), run_time=0.5)
        self.at(n.cue(0, "large") + 1.5, FadeOut(big), run_time=0.4)

        # beat 1: the sentence and the limits
        sentence = fbox(fault, 0.05, 0.155, 0.47, 0.19)
        limits = fbox(fault, 0.05, 0.2, 0.95, 0.225)
        self.at(n.cue(1, "sentence"), Create(sentence), run_time=0.5)
        keys = VGroup(tag("NORMAL up to 5%", color=MID, size=22), tag("WARNING up to 10%", color=LIME, size=22),
                      tag("ABNORMAL beyond", color=OLIVE, size=22)).arrange(DOWN, buff=0.35).move_to([0, 0.2, 0])
        self.at(n.cue(1, "limits"), Create(limits), LaggedStart(*[FadeIn(k) for k in keys], lag_ratio=0.3), run_time=0.7)
        self.at(n.cue(1, "limits") + 2.0, FadeOut(sentence), FadeOut(limits), FadeOut(keys), run_time=0.4)

        # beat 2: the four totals, each with a one-line definition in the middle
        tiles = {"peak": (0.056, 0.641, 0.424, 0.76), "energy": (0.46, 0.641, 0.944, 0.76),
                 "samples": (0.056, 0.777, 0.424, 0.893), "elapsed": (0.46, 0.777, 0.944, 0.893)}
        defs = {"peak": "Peak power: the highest measured power so far",
                "energy": "Energy: how much the plant has produced",
                "samples": "Samples: how many readings so far",
                "elapsed": "Elapsed: simulated time since the run began"}
        current = None
        for word in ("peak", "energy", "samples", "elapsed"):
            a, b, c, d = tiles[word]
            box = fbox(fault, a, b, c, d)
            text = Text(defs[word], font_size=24, color=INK, line_spacing=0.9).move_to([0, 0.2, 0])
            anims = [Create(box), FadeIn(text)]
            if current is not None:
                anims += [FadeOut(current[0]), FadeOut(current[1])]
            self.at(n.cue(2, word), *anims, run_time=0.5)
            current = (box, text)
        self.at(n.start(3), FadeOut(current[0]), FadeOut(current[1]), FadeOut(healthy), FadeOut(fault),
                FadeOut(h_lab), FadeOut(f_lab), run_time=0.6)

        # beat 3: the state chip in the header of the dashboard
        chip_img = shot("simple_06_dashboard_fault.png", width=8.0, crop=(0.55, 0.0, 1.0, 0.1)).move_to([0, 1.0, 0])
        self.at(n.start(3), FadeIn(chip_img), run_time=0.5)
        chip = fbox(chip_img, 0.69, 0.25, 0.985, 0.8)
        chip_note = tag("SYSTEM STATE: ABNORMAL", color=OLIVE, size=24).move_to([0, -0.2, 0])
        self.at(n.cue(3, "chip"), Create(chip), FadeIn(chip_note), run_time=0.6)
        self.finish()


class Try(Narrated):
    scene_id = "try"

    def construct(self):
        n = self.n
        self.header()
        steps = ["Speed 600x,\npress Start", "Wait for the sun,\nthen click Partial shading",
                 "Deviation falls, state\nturns abnormal", "Clear all removes\nthe fault"]
        rows = VGroup()
        for i, text in enumerate(steps):
            row = VGroup(tag(str(i + 1), size=22), Text(text, font_size=24, color=INK, line_spacing=0.9))
            row.arrange(RIGHT, buff=0.3)
            rows.add(row)
        rows.arrange(DOWN, buff=0.7, aligned_edge=LEFT).move_to([-4.6, 0.1, 0])
        idle = shot("simple_01_dashboard_idle.png", width=7.5).move_to([2.7, 0.1, 0])
        self.at(n.start(0), FadeIn(rows[0]), FadeIn(idle))
        start_box = fbox(idle, 0.175, 0.125, 0.22, 0.165)
        self.at(n.cue(0, "start"), Create(start_box), run_time=0.5)

        normal = shot("simple_02_dashboard_normal.png", width=7.5).move_to([2.7, 0.1, 0])
        partial_box = fbox(normal, 0.595, 0.125, 0.668, 0.165)
        self.at(n.start(1), FadeIn(rows[1]), FadeOut(idle), FadeOut(start_box), FadeIn(normal), run_time=0.6)
        self.at(n.cue(1, "partial"), Create(partial_box), run_time=0.5)

        fault = shot("simple_06_dashboard_fault.png", width=7.5).move_to([2.7, 0.1, 0])
        dev_box = fbox(fault, 0.757, 0.275, 0.99, 0.975)
        chart_box = fbox(fault, 0.17, 0.34, 0.76, 0.975)
        self.at(n.start(2), FadeIn(rows[2]), FadeOut(normal), FadeOut(partial_box), FadeIn(fault), run_time=0.6)
        self.at(n.cue(2, "abnormal"), Create(dev_box), Create(chart_box), run_time=0.5)

        clear_box = fbox(fault, 0.94, 0.125, 0.98, 0.165)
        self.at(n.start(3), FadeIn(rows[3]), FadeOut(dev_box), FadeOut(chart_box), run_time=0.5)
        self.at(n.cue(3, "clear"), Create(clear_box), run_time=0.5)
        self.finish()


class Log(Narrated):
    scene_id = "log"

    def construct(self):
        n = self.n
        self.header()
        g = shot("simple_10_event_log.png", width=8.6)
        self.at(n.start(0), FadeIn(g))
        alarms = fbox(g, 0.18, 0.128, 0.986, 0.544)
        self.at(n.cue(0, "alarms"), Create(alarms), run_time=0.5)
        cause = Line(fp(g, 0.337, 0.283), fp(g, 0.402, 0.283), color=OLIVE, stroke_width=5)
        self.at(n.cue(0, "cause"), Create(cause), run_time=0.5)

        ack = fbox(g, 0.888, 0.205, 0.966, 0.244)
        self.at(n.cue(1, "acknowledge"), Create(ack), run_time=0.5)
        reset_pill = tag("Reset clears alarms", color=OLIVE, size=22).move_to(fp(g, 0.5, 0.78))
        self.at(n.cue(1, "reset"), FadeIn(reset_pill), run_time=0.5)

        self.at(n.start(2), FadeOut(alarms), FadeOut(cause), FadeOut(ack), FadeOut(reset_pill), run_time=0.5)
        events = fbox(g, 0.18, 0.56, 0.986, 0.974)
        self.at(n.cue(2, "events"), Create(events), run_time=0.5)

        self.at(n.start(3), FadeOut(events), run_time=0.4)
        show_log = fbox(g, 0.916, 0.052, 0.985, 0.091)
        self.at(n.cue(3, "log"), Create(show_log), run_time=0.5)
        tip = callout("the reason\nis in the log", tag="TIP", color=OLIVE, size=24, width=3.0).move_to([5.4, 0.9, 0])
        self.at(n.cue(3, "log") + 0.6, FadeIn(tip), Create(Arrow(tip.get_top(), show_log.get_bottom() + DOWN * 0.0, buff=0.05, color=OLIVE, stroke_width=4)), run_time=0.6)
        self.finish()


class Pages(Narrated):
    scene_id = "pages"

    def construct(self):
        n = self.n
        self.header()
        trends = shot("simple_08_trends.png", width=8.6)
        self.at(n.start(0), FadeIn(trends))
        first = fbox(trends, 0.179, 0.128, 0.576, 0.399)
        self.at(n.cue(0, "trends"), Create(first), run_time=0.5)
        corners = [(0.52, 0.16), (0.94, 0.16), (0.52, 0.45), (0.94, 0.45), (0.52, 0.74)]
        marks = VGroup(*[tag(str(i + 1), size=20).move_to(fp(trends, x, y)) for i, (x, y) in enumerate(corners)])
        self.at(n.cue(0, "channel"), LaggedStart(*[FadeIn(m) for m in marks], lag_ratio=0.15))
        self.at(n.start(1), FadeOut(trends), FadeOut(first), FadeOut(marks), run_time=0.5)

        data = shot("simple_09_data.png", width=8.6)
        table = fbox(data, 0.179, 0.128, 0.986, 0.977)
        self.at(n.start(1), FadeIn(data), run_time=0.5)
        self.at(n.cue(1, "data"), Create(table), run_time=0.5)
        export = fbox(data, 0.902, 0.049, 0.986, 0.095)
        self.at(n.cue(1, "export"), Create(export), run_time=0.5)

        self.at(n.start(2), FadeOut(data), FadeOut(table), FadeOut(export), run_time=0.5)
        model = shot("simple_11_model.png", width=8.6)
        circuit = fbox(model, 0.186, 0.16, 0.575, 0.552)
        self.at(n.start(2), FadeIn(model), run_time=0.5)
        self.at(n.cue(2, "circuit"), Create(circuit), run_time=0.5)
        curves = fbox(model, 0.18, 0.944, 0.99, 0.995)
        curves_pill = tag("curves below", color=FOREST, size=22).move_to([5.6, -1.6, 0])
        self.at(n.cue(2, "curves"), Create(curves), FadeIn(curves_pill), run_time=0.6)

        # beat 3: the Live Feed page, with a pointer to tutorial 7 (sidebar item at about y 0.445 of the 1422 x 995 image)
        self.at(n.start(3), FadeOut(model), FadeOut(circuit), FadeOut(curves), FadeOut(curves_pill), run_time=0.5)
        live = shot("simple_24_live_page.png", width=8.2)
        item = fbox(live, 0.01, 0.42, 0.152, 0.47)
        t7 = tag("Tutorial 7", color=FOREST, size=26).move_to([5.4, 0.0, 0])
        self.at(n.start(3), FadeIn(live), run_time=0.5)
        self.at(n.cue(3, "Live"), Create(item), run_time=0.5)
        self.at(n.cue(3, "seven"), FadeIn(t7, shift=LEFT * 0.3), run_time=0.5)
        self.finish()


class Look(Narrated):
    scene_id = "look"

    def construct(self):
        n = self.n
        self.header()
        hidden = shot("simple_12_sidebar_hidden.png", width=8.6)
        self.at(n.start(0), FadeIn(hidden))
        hide_pill = tag("Hide: bottom of the sidebar", color=FOREST, size=22).move_to([5.2, 2.0, 0])
        self.at(n.cue(0, "hide"), FadeIn(hide_pill), run_time=0.5)
        menu = fbox(hidden, 0.008, 0.04, 0.045, 0.095)
        self.at(n.cue(0, "menu"), Create(menu), run_time=0.5)
        self.at(n.start(1), FadeOut(hidden), FadeOut(hide_pill), FadeOut(menu), run_time=0.5)

        view = shot("simple_13_view_menu.png", width=3.0).move_to([-2.2, 0.2, 0])
        self.at(n.start(1), FadeIn(view), run_time=0.5)
        sidebar_item = fbox(view, 0.02, 0.63, 0.98, 0.78)
        self.at(n.cue(1, "control"), Create(sidebar_item), run_time=0.5)
        keys = VGroup(tag("Ctrl+B", color=FOREST, size=24), tag("Esc", color=FOREST, size=24)).arrange(DOWN, buff=0.4)
        keys.move_to([3.4, 0.2, 0])
        self.at(n.cue(1, "control"), FadeIn(keys), run_time=0.5)
        colours = fbox(view, 0.02, 0.04, 0.98, 0.42)
        self.at(n.cue(1, "view"), Create(colours), run_time=0.5)

        self.at(n.start(2), FadeOut(view), FadeOut(sidebar_item), FadeOut(colours), FadeOut(keys), run_time=0.5)
        dark = shot("simple_17_dashboard_dark.png", width=8.6)
        self.at(n.start(2), FadeIn(dark), run_time=0.5)
        self.at(n.cue(2, "dark"), FadeIn(tag("Dark", size=26).move_to([5.5, 2.0, 0])), run_time=0.5)
        self.finish()


class Recap(Narrated):
    scene_id = "recap"

    def construct(self):
        n = self.n
        self.header()
        items = ["Start the run on the Dashboard", "Read the deviation card",
                 "Inject a fault in daylight", "Follow the alarm in the event log"]
        cues = ["start", "deviation", "inject", "alarm"]
        rows = VGroup()
        for i, text in enumerate(items):
            rows.add(VGroup(tag(str(i + 1), size=26), label(text, size=32, color=INK)).arrange(RIGHT, buff=0.35))
        rows.arrange(DOWN, buff=0.45, aligned_edge=LEFT).move_to([0, 0.1, 0])
        card_ = card(9.5, 4.6).move_to([0, 0.1, 0])
        self.at(n.start(0), FadeIn(card_))
        for row, word in zip(rows, cues):
            self.at(n.cue(0, word), FadeIn(row), run_time=0.5)
        self.at(n.start(1), FadeOut(card_), FadeOut(rows), run_time=0.5)
        nxt = tag("Tutorial 5: your own data", color=MID, size=40).move_to([0, 0.1, 0])
        self.at(n.start(1), FadeIn(nxt, shift=UP * 0.3), run_time=0.6)
        self.finish()
