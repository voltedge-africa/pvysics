"""PV Digital Twin, Tutorial 7: Connecting a live feed: scenes (the Manim animation of each scene, cued to the narration in script.json)."""
import numpy as np

from common import *

MONO = "DejaVu Sans Mono"                              # code, the terminal card and file names
W, H = 1422, 995                                       # pixel size of the screenshots in docs/screenshots
LIVE_CROP = (240 / W, 100 / H, 1410 / W, 527 / H)      # Listen, token, start/stop and the send address of the Live Feed page
STATUS_CROP = (213 / W, 776 / H, 1.0, 1.0)             # the Status card of the Live Feed page
DASH_CROP = (0.16, 0.0, 1.0, 0.62)                     # the top band of the dashboard (sidebar cut off)


def pxbox(group, crop, x0, y0, x1, y1, pad=5):
    """A lime box round the pixels (x0, y0)-(x1, y1) of a full-size screenshot, for a shot made with `crop`."""
    cx0, cy0, cx1, cy1 = crop
    fx = lambda px: (px / W - cx0) / (cx1 - cx0)
    fy = lambda py: (py / H - cy0) / (cy1 - cy0)
    return shot_region(group, fx(x0 - pad), fy(y0 - pad), fx(x1 + pad), fy(y1 + pad))


def at_left(mob, x, y):
    """Place `mob` with its left edge at x and its centre at height y."""
    return mob.move_to([x + mob.width / 2, y, 0])


def code_card(lines, size=22, pad=0.32, header=0.0, width=None, gap=0.16):
    """A dark-green rounded card of monospace lines (Text in DejaVu Sans Mono). `card.box`, `card.lines[i]` for reveals."""
    rows = [Text(s, font=MONO, font_size=size, color=BG) for s in lines]
    body = VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=gap)
    box = RoundedRectangle(corner_radius=0.18, width=width or body.width + 2 * pad, height=body.height + 2 * pad + header,
                           stroke_width=0, fill_color=FOREST, fill_opacity=1)
    body.move_to(box.get_top() + DOWN * (pad + header + body.height / 2)).align_to(box, LEFT).shift(RIGHT * pad)
    card = VGroup(box, *rows)
    card.box, card.lines = box, rows
    return card


def terminal(lines, size=22, width=10.6):
    """The code card with three lime dots at its top left, as a terminal window."""
    card = code_card(lines, size=size, header=0.5, width=width)
    dots = VGroup(*[Dot(radius=0.075, color=LIME) for _ in range(3)]).arrange(RIGHT, buff=0.22)
    dots.move_to(card.box.get_top() + DOWN * 0.3 + RIGHT * (-card.box.width / 2 + 0.55))
    card.add(dots)
    return card


def json_row(pieces, size=24):
    """One line of JSON as separate Text pieces on a dark-green card, so each key can be boxed on its own."""
    texts = [Text(s, font=MONO, font_size=size, color=BG) for s in pieces]
    row = VGroup(*texts).arrange(RIGHT, buff=0.22)
    box = RoundedRectangle(corner_radius=0.18, width=row.width + 0.7, height=row.height + 0.6, stroke_width=0,
                           fill_color=FOREST, fill_opacity=1).move_to(row)
    card = VGroup(box, *texts)
    card.box, card.pieces = box, texts
    return card


def tick_at(x, y):
    return polyline([(x - 0.13, y - 0.01, 0), (x - 0.04, y - 0.12, 0), (x + 0.15, y + 0.14, 0)], color=FOREST, stroke_width=6)


def cross_at(x, y, s=0.14):
    return VGroup(Line([x - s, y - s, 0], [x + s, y + s, 0], color=OLIVE, stroke_width=6),
                  Line([x - s, y + s, 0], [x + s, y - s, 0], color=OLIVE, stroke_width=6))


class Idea(Narrated):
    scene_id = "idea"

    def construct(self):
        n = self.n
        self.header()
        y = 0.5                                                         # the row of the diagram
        before = pill("so far: simulated, or from a file", color=PALE, text_color=INK, size=22).move_to([0, 2.25, 0])
        esp = block("ESP32", width=2.3, height=1.3, size=30).move_to([-3.0, y, 0])
        sensors = VGroup(*[pill(s, color=MID, size=22) for s in "GTVI"]).arrange(DOWN, buff=0.22).move_to([-5.9, y, 0])
        feed_in = flow_arrow([-5.2, y, 0], [-4.25, y, 0])
        node = [-0.5, y, 0]
        wifi = VGroup(*[Arc(radius=r, start_angle=PI / 4, angle=PI / 2, arc_center=node, stroke_color=MID, stroke_width=6)
                        for r in (0.3, 0.6, 0.9)], Dot(node, radius=0.09, color=LIME))
        net = label("network", size=22, color=INK).move_to([node[0], y - 0.4, 0])
        feed_mid = flow_arrow([-1.8, y, 0], [0.85, y, 0])
        app = RoundedRectangle(corner_radius=0.15, width=5.0, height=2.3, stroke_color=FOREST, stroke_width=4,
                               fill_color=WHITE, fill_opacity=1).move_to([3.4, y, 0])
        app_name = Text("PV Digital Twin app", font_size=26, color=FOREST, weight=BOLD).move_to([3.4, y + 0.75, 0])
        # beat 1: the message travels to the app, which scores it
        msg = code_card(["{ g, t, v, i }"], size=22, pad=0.3).move_to([-3.0, y, 0])
        scored = VGroup(*[pill(s, color=MID, size=20) for s in ("twin", "deviation", "state")]).arrange(RIGHT, buff=0.4)
        scored.move_to([3.4, 0.2, 0])
        score_arrows = VGroup(*[flow_arrow(a.get_right() + RIGHT * 0.04, b.get_left() + LEFT * 0.04, width=3)
                                for a, b in zip(scored[:-1], scored[1:])])
        cells = VGroup(*[VGroup(Square(0.5, stroke_color=MID, stroke_width=3, fill_color=PALE, fill_opacity=1),
                                Text(c, font=MONO, font_size=20, color=FOREST).move_to(Square(0.5)))
                         for c in "gtvi"]).arrange(RIGHT, buff=0)
        for cell in cells:
            cell[1].move_to(cell[0])
        row = cells.move_to([1.6, -1.75, 0])
        dataset = VGroup(pill("a live reading", color=MID, size=20).move_to([-2.6, -1.75, 0]),
                         tex("=", size=54, color=FOREST).move_to([-0.5, -1.75, 0]),
                         row, label("a row of a dataset", size=22, color=INK).next_to(row, RIGHT, buff=0.3))
        # beat 2: the prediction and the comparison, under the app
        pred = label("predicted at the measured voltage", size=26, color=MID)
        minus = tex("-", size=60, color=OLIVE)
        meas = label("measured power = V x I", size=26, color=INK)
        compare = VGroup(pred, minus, meas).arrange(RIGHT, buff=0.35).move_to([0, -1.75, 0])

        self.at(n.start(0), FadeIn(before))
        self.at(n.cue(0, "live"), FadeOut(before))
        self.at(n.cue(0, "device"), FadeIn(esp))
        self.at(n.cue(0, "sensor"), FadeIn(sensors), Create(feed_in))
        self.at(n.cue(0, "happen"), FadeIn(wifi), FadeIn(net), Create(feed_mid), FadeIn(app), FadeIn(app_name))
        self.at(n.cue(1, "message"), FadeIn(msg))
        self.at(19.93, msg.animate.move_to([2.2, y, 0]), run_time=2.0)
        self.at(n.cue(1, "scores"), FadeOut(msg), LaggedStart(*[FadeIn(p) for p in scored], lag_ratio=0.4),
                FadeIn(score_arrows))
        self.at(n.cue(1, "dataset"), FadeIn(dataset))
        self.at(n.cue(2, "predicts"), FadeOut(dataset), FadeIn(pred))
        self.at(n.cue(2, "compares"), FadeIn(minus), FadeIn(meas))
        self.finish()


class Start(Narrated):
    scene_id = "start"

    def construct(self):
        n = self.n
        self.header()
        live = shot("simple_24_live_page.png", width=12.0, crop=LIVE_CROP).move_to([0, 0.2, 0])

        def box(*px):
            return pxbox(live, LIVE_CROP, *px)

        port_box = box(267, 168, 555, 212)
        devices_box = box(352, 272, 690, 295)
        token_box = box(352, 298, 1180, 343)
        copy_box = box(1182, 302, 1288, 340)
        new_box = box(1290, 302, 1388, 340)
        start_box = box(264, 347, 419, 391)
        address_box = box(264, 475, 772, 516)
        stop_box = box(421, 350, 490, 389)
        ticked = pill("ticked: devices on your Wi-Fi may send", color=MID, text_color=WHITE, size=22).move_to([0, -2.5, 0])
        clear = pill("clear: this computer only", color=PALE, text_color=INK, size=22).move_to([0, -2.5, 0])

        self.at(n.start(0), FadeIn(live))
        self.at(n.cue(0, "port"), FadeIn(port_box))
        self.at(n.cue(0, "devices"), FadeOut(port_box), FadeIn(devices_box))
        self.at(n.cue(1, "tick"), FadeIn(ticked))
        self.at(n.cue(1, "clear"), FadeOut(ticked), FadeIn(clear))
        self.at(n.start(2), FadeOut(clear))
        self.at(n.cue(2, "token"), FadeOut(devices_box), FadeIn(token_box))
        self.at(n.cue(2, "Copy"), FadeOut(token_box), FadeIn(copy_box))
        self.at(n.cue(2, "new"), FadeOut(copy_box), FadeIn(new_box))
        self.at(n.cue(3, "start"), FadeOut(new_box), FadeIn(start_box))
        self.at(n.cue(3, "address"), FadeOut(start_box), FadeIn(address_box))
        self.at(n.cue(4, "stop"), FadeOut(address_box), FadeIn(stop_box))
        self.finish()


class Message(Narrated):
    scene_id = "message"

    def construct(self):
        n = self.n
        self.header()
        # beat 0: the request line by line
        request = code_card(["POST /reading", "X-Api-Key: <your token>"], size=28, pad=0.4).move_to([0, 0.5, 0])
        self.at(n.start(0), FadeIn(request.box))
        self.at(n.cue(0, "post"), FadeIn(request.lines[0]))
        self.at(n.cue(0, "header"), FadeIn(request.lines[1]))
        # beat 1: the reading, each key boxed as it is explained, with a table of the keys
        reading = json_row(['{"g": 640.0,', '"t": 32.5,', '"v": 29.0,', '"i": 5.2}']).move_to([0, 2.0, 0])
        self.at(n.start(1), FadeOut(request), FadeIn(reading))
        keys = [("g", "irradiance, W/m²"), ("t", "module temperature, °C"), ("v", "voltage, V"), ("i", "current, A")]
        rows = []
        for k, (key, desc) in enumerate(keys):
            ky = 0.9 - 0.6 * k
            kt = Text(key, font=MONO, font_size=26, color=FOREST, weight=BOLD)
            dt = Text(desc, font_size=26, color=INK)
            rows.append(VGroup(at_left(kt, -4.6, ky), at_left(dt, -4.0, ky)))
        table, key_boxes = VGroup(*rows), VGroup()
        cues = [n.cue(1, "G"), n.cue(1, "t"), n.cue(1, "v"), n.cue(1, "i")]
        for k, (row, t) in enumerate(zip(rows, cues)):
            key_box = SurroundingRectangle(reading.pieces[k], color=LIME, buff=0.08, stroke_width=4)
            key_boxes.add(key_box)
            self.at(t, FadeIn(row), Create(key_box))
        # beat 2: power from voltage and current, under the key table
        formula = tex(r"\text{power} = v \times i", size=50, color=FOREST).move_to([-3.0, -1.8, 0])
        tip = callout("send v and i, not power", tag="TIP", color=OLIVE, size=24).move_to([3.6, -1.9, 0])
        self.at(n.cue(2, "times"), FadeIn(formula))
        self.at(n.cue(2, "instead"), FadeIn(tip))
        # beat 3: the timestamp, as a fifth line of the JSON
        self.at(n.start(3), FadeOut(reading), FadeOut(table), FadeOut(key_boxes), FadeOut(formula), FadeOut(tip))
        full = code_card(['{', '  "g": 640.0,', '  "t": 32.5,', '  "v": 29.0,', '  "i": 5.2,',
                          '  "timestamp": "2025-01-15T10:00:00"', '}'], size=24).move_to([-1.2, 0.4, 0])
        stamp_line = full.lines[5]
        stamp_box = SurroundingRectangle(stamp_line, color=LIME, buff=0.08, stroke_width=4)
        optional = pill("optional", color=MID, size=20).move_to([stamp_line.get_right()[0] + 1.3, stamp_line.get_y(), 0])
        self.at(n.start(3), FadeIn(full.box), *[FadeIn(l) for l in full.lines[:5]], FadeIn(full.lines[6]))
        self.at(n.cue(3, "timestamp"), FadeIn(stamp_line), Create(stamp_box), FadeIn(optional))
        # beat 4: the reply, one row per status code
        self.at(n.start(4), FadeOut(full), FadeOut(stamp_box), FadeOut(optional))
        replies = [("202", MID, "the readings were taken", FOREST),
                   ("401", OLIVE, "token missing or wrong", OLIVE),
                   ("422", OLIVE, "every reading refused; the reply says why", OLIVE)]
        for k, (code, color, text, tcolor) in enumerate(replies):
            ry = 1.2 - 1.3 * k
            code_pill = pill(code, color=color, text_color=WHITE, size=30).move_to([-4.2, ry, 0])
            desc = Text(text, font_size=28, color=tcolor, weight=BOLD if k else NORMAL)
            desc = at_left(desc, -3.0, ry)
            self.at(n.cue(4, ["two", "four", "twenty"][k]), FadeIn(code_pill), FadeIn(desc))
        self.finish()


class Try(Narrated):
    scene_id = "try"

    def construct(self):
        n = self.n
        self.header()
        term = terminal([
            "$ curl -X POST http://127.0.0.1:8765/reading \\",
            "    -H 'X-Api-Key: <your token>' \\",
            "    -H 'Content-Type: application/json' \\",
            "    -d '{\"g\": 640.0, \"t\": 32.5, \"v\": 29.0, \"i\": 5.2}'",
        ], size=22).move_to([0, 0.2, 0])
        cursor = Rectangle(width=0.13, height=0.28, fill_color=LIME, fill_opacity=1, stroke_width=0)
        cursor.move_to(term.lines[-1].get_right() + RIGHT * 0.2)
        self.at(n.cue(0, "curl"), FadeIn(term))
        self.at(n.cue(0, "terminal"), FadeIn(cursor))
        self.at(n.cue(0, "enter"), Circumscribe(term.box, color=LIME), run_time=1.0)
        # beat 1: the dashboard takes its place
        dash = shot("simple_25_live_dashboard.png", width=9.0, crop=DASH_CROP).move_to([0, 0.0, 0])

        def box(*px):
            return pxbox(dash, DASH_CROP, *px)

        self.at(n.start(1), FadeOut(term), FadeOut(cursor), FadeIn(dash))
        self.at(n.cue(1, "Dashboard"), FadeIn(box(1088, 36, 1232, 64)))
        chart_box = box(262, 300, 470, 470)
        self.at(n.cue(1, "chart"), FadeOut(box(1088, 36, 1232, 64)), FadeIn(chart_box))
        status = pill("status on the Live Feed page: one reading accepted", color=MID, size=20).move_to([0, -2.65, 0])
        self.at(n.cue(1, "status"), FadeOut(chart_box), FadeIn(status))
        # beat 2: the controls are locked while a feed is the source
        self.at(n.start(2), FadeOut(status))
        toolbar_box = box(244, 104, 1404, 156)
        self.at(n.cue(2, "speed"), FadeIn(toolbar_box))
        body = RoundedRectangle(corner_radius=0.05, width=0.42, height=0.32, stroke_width=0, fill_color=FOREST, fill_opacity=1)
        shackle = Arc(radius=0.12, start_angle=0, angle=PI, arc_center=body.get_top(), stroke_color=FOREST, stroke_width=6)
        lock = VGroup(shackle, body).move_to([5.3, 1.43, 0])
        self.at(n.cue(2, "controls"), FadeIn(lock))
        self.at(n.cue(2, "nothing"), Indicate(lock, color=LIME))
        # beat 3: the clock beside the controls
        self.at(n.start(3), FadeOut(toolbar_box))
        self.at(n.cue(3, "clock"), FadeIn(box(640, 118, 760, 144)))
        self.finish()


class Gaps(Narrated):
    scene_id = "gaps"

    def construct(self):
        n = self.n
        self.header()

        def hx(hour):
            return -5.8 + hour * (11.6 / 24)

        axis = Line([hx(0), 0, 0], [hx(24), 0, 0], color=MUTE, stroke_width=3)
        ticks = VGroup(*[VGroup(Line([hx(h), 0, 0], [hx(h), -0.12, 0], color=MUTE, stroke_width=3),
                                Text(f"{h:02d}:00", font_size=20, color=INK).move_to([hx(h), -0.42, 0]))
                         for h in (0, 6, 12, 18, 24)])
        empty = Rectangle(width=hx(13) - hx(0), height=1.5, fill_color=PALE, fill_opacity=0.55, stroke_width=0)
        empty.move_to([(hx(0) + hx(13)) / 2, 0.75, 0])
        no_morning = pill("no morning expected", color=PALE, text_color=INK, size=20).move_to([-3.4, 0.75, 0])
        no_alarm = pill("no alarm", color=MID, text_color=WHITE, size=20).move_to([-0.9, 0.75, 0])
        hours = [h for h in np.arange(13.0, 24.01, 0.5) if not (17.0 <= h <= 17.5)]
        dots = VGroup(*[Dot([hx(h), 0, 0], radius=0.09, color=LIME) for h in hours])
        gap_label = label("gap: nothing raised", size=22, color=INK).move_to([hx(17.25), 0.7, 0])

        self.at(n.start(0), FadeIn(empty), Create(axis), FadeIn(ticks), FadeIn(no_morning), FadeIn(no_alarm))
        self.at(n.cue(0, "midday"), LaggedStart(*[FadeIn(d) for d in dots], lag_ratio=0.1))
        self.at(n.cue(0, "gap"), FadeIn(gap_label))
        # beat 1: silence is shown separately, on the dashboard
        timeline = VGroup(empty, axis, ticks, no_morning, no_alarm, dots, gap_label)
        dash = shot("simple_26_live_no_data.png", width=8.4, crop=DASH_CROP).move_to([0, 0.0, 0])
        chip_box = pxbox(dash, DASH_CROP, 1248, 40, 1406, 60)
        limit = pill("no data after 30 s", color=OLIVE, text_color=WHITE, size=22).move_to([0, -2.6, 0])
        self.at(n.start(1), FadeOut(timeline), FadeIn(dash))
        self.at(n.cue(1, "thirty"), FadeIn(limit))
        self.at(n.cue(1, "amber"), FadeIn(chip_box))
        # beat 2: back to a normal reading
        self.at(n.start(2), FadeOut(dash), FadeOut(chip_box), FadeOut(limit))
        no_box = RoundedRectangle(corner_radius=0.18, width=2.7, height=0.95, stroke_color=OLIVE, stroke_width=5,
                                  fill_color=WHITE, fill_opacity=1).move_to([-3.2, 0.2, 0])
        no_text = Text("NO DATA", font_size=28, color=OLIVE, weight=BOLD).move_to(no_box)
        norm_box = RoundedRectangle(corner_radius=0.18, width=2.7, height=0.95, stroke_color=MID, stroke_width=3,
                                    fill_color=MID, fill_opacity=1).move_to([3.2, 0.2, 0])
        norm_text = Text("NORMAL", font_size=28, color=WHITE, weight=BOLD).move_to(norm_box)
        resume = VGroup(flow_arrow([-1.8, 0.2, 0], [1.8, 0.2, 0], width=5),
                        label("readings resume", size=24, color=INK).move_to([0, 0.85, 0]))
        self.at(n.start(2), FadeIn(no_box), FadeIn(no_text), FadeIn(norm_box), FadeIn(norm_text))
        self.at(n.cue(2, "resume"), FadeIn(resume))
        # beat 3: a silent device is not normal
        sketch = VGroup(no_box, no_text, norm_box, norm_text, resume)
        callout_box = callout("Silence is not Normal", tag="TRAP", color=OLIVE, size=34).move_to([0, 0.2, 0])
        self.at(n.cue(3, "never"), FadeOut(sketch), FadeIn(callout_box))
        self.at(n.cue(3, "chip"), Indicate(callout_box, color=LIME))
        self.finish()


class Keep(Narrated):
    scene_id = "keep"

    def construct(self):
        n = self.n
        self.header()
        status = shot("simple_24_live_page.png", width=12.0, crop=STATUS_CROP).move_to([0, 0.95, 0])
        csv_box = pxbox(status, STATUS_CROP, 262, 920, 682, 942)
        named = pill("named from the start time", color=MID, size=22).move_to([0, -0.7, 0])
        # beat 0: where the readings are kept
        self.at(n.start(0), FadeIn(status))
        self.at(n.cue(0, "written"), FadeIn(csv_box))
        self.at(n.cue(0, "named"), FadeIn(named))
        # beat 1: import the file and score the day again
        file_card = code_card(["live-...csv"], size=24).move_to([-3.2, 0.2, 0])
        analysis = pill("Analysis > Dataset", color=MID, size=24).move_to([3.0, 0.2, 0])
        feed = flow_arrow([-1.9, 0.2, 0], [1.2, 0.2, 0], width=5)
        self.at(n.start(1), FadeOut(status), FadeOut(csv_box), FadeOut(named),
                FadeIn(file_card), Create(feed), FadeIn(analysis))
        # beat 2: a reading is refused for three reasons
        heading = Text("A reading is refused if:", font_size=34, color=FOREST, weight=BOLD)
        at_left(heading, -5.8, 1.7)
        refused = VGroup(heading)
        items = [("value missing or not a number", 0.7, n.cue(2, "missing")),
                 ("irradiance negative", -0.2, n.cue(2, "negative")),
                 ("time not after the last reading", -1.1, n.cue(2, "after"))]
        self.at(n.start(2), FadeOut(file_card), FadeOut(feed), FadeOut(analysis), FadeIn(heading))
        for text, iy, t in items:
            reason = at_left(Text(text, font_size=28, color=INK), -5.3, iy)
            cross = cross_at(-5.8, iy)
            refused.add(reason, cross)
            self.at(t, FadeIn(cross), FadeIn(reason))
        # beat 3: the limits
        self.at(n.start(3), FadeOut(refused), run_time=0.4)
        limits_head = at_left(Text("Know the limits", font_size=40, color=FOREST, weight=BOLD), -5.8, 1.9)
        self.at(n.cue(3, "limits"), FadeIn(limits_head))
        limits = VGroup(limits_head)
        for text, ly, t in [("plain HTTP: not encrypted", 0.7, n.cue(3, "plain")),
                            ("one module, one feed", -0.2, n.cue(3, "one")),
                            ("history grows while it runs", -1.1, n.cue(3, "grows"))]:
            bar = Rectangle(width=0.14, height=0.5, fill_color=OLIVE, fill_opacity=1, stroke_width=0).move_to([-6.0, ly, 0])
            line = at_left(Text(text, font_size=30, color=OLIVE, weight=BOLD), -5.7, ly)
            limits.add(bar, line)
            self.at(t, FadeIn(bar), FadeIn(line))
        # beat 4: what to do on the module and the sensors
        self.at(n.start(4), FadeOut(limits), run_time=0.4)
        checks = [("module temperature, not air temperature", 1.0, n.cue(4, "temperature")),
                  ("sensor ranges checked against your module", 0.0, n.cue(4, "ranges"))]
        for text, cy, t in checks:
            self.at(t, FadeIn(tick_at(-5.8, cy)), FadeIn(at_left(Text(text, font_size=30, color=INK), -5.3, cy)))
        sketch_file = code_card(["docs/esp32/pvysics_feed.ino (untested)"], size=24)
        sketch_file.move_to([-5.8 + sketch_file.width / 2, -1.6, 0])
        self.at(n.cue(4, "sketch"), FadeIn(sketch_file))
        self.finish()


class Recap(Narrated):
    scene_id = "recap"

    def construct(self):
        n = self.n
        self.header()
        items = [("device → POST /reading + token", 1.7, n.cue(0, "device")),
                 ("app scores each reading as it arrives", 0.7, n.cue(0, "app")),
                 ("silence = NO DATA, not Normal", -0.3, n.cue(1, "silence")),
                 ("every reading saved: analyse it later", -1.3, n.cue(1, "file"))]
        shown = []
        for text, ry, t in items:
            line = VGroup(tick_at(-5.8, ry), at_left(Text(text, font_size=32, color=INK), -5.3, ry))
            shown.append(line)
            self.at(t, FadeIn(line))
        end = pill("Tutorials 1 to 7", color=MID, text_color=WHITE, size=40).move_to([0, 0.3, 0])
        self.at(16.0, *[FadeOut(s) for s in shown], FadeIn(end))
        self.finish()
