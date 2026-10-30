"""PV Digital Twin, Tutorial 6: Limits and trust: scenes (the Manim animation of each scene, cued to the narration in script.json)."""
import numpy as np

from common import *
from pvysics.run import bundled_run_config
from pvysics.validation import fault_batch

AX_Y = -0.7                       # the deviation axis of the first scene
SC = 0.13                         # scene units per percentage point of deviation (axis of the first scene)
HX0, HSC, HB = -5.0, 4.5, -1.6    # histogram: x of 0 %, scene units per percentage point, baseline


def _hx(v):
    return HX0 + v * HSC


def _curves(samples):
    """Hours, measured and predicted power of a run's samples (the same reading as pvdata.day)."""
    origin = samples[0].timestamp
    hours = np.array([(s.timestamp - origin) / np.timedelta64(1, "h") for s in samples])
    return hours, np.array([s.power_measured for s in samples]), np.array([s.power_predicted for s in samples])


def _dots(values, y0, spread, color, rng):
    return VGroup(*[Dot([v * SC, y0 + rng.uniform(0, spread), 0], radius=0.045, color=color) for v in values])


def _thumb(title, hours, measured, predicted, fault=False):
    """A small day curve: measured (solid, INK) and twin (dashed, MID), with the one-hour fault shaded olive."""
    keep = (hours >= 5) & (hours <= 18)
    hours, measured, predicted = hours[keep], measured[keep], predicted[keep]
    ax = small_axes([5, 18], [0, 120], 3.3, 1.35)
    parts = []
    if fault:
        width = ax.c2p(11, 0)[0] - ax.c2p(10, 0)[0]
        parts.append(Rectangle(width=width, height=1.35, fill_color=OLIVE, fill_opacity=0.25, stroke_width=0)
                     .move_to(ax.c2p(10.5, 60)))
    parts.append(ax)
    parts.append(trace(ax, hours, measured, color=INK, stroke_width=3))
    parts.append(DashedVMobject(trace(ax, hours, predicted, color=MID, stroke_width=3), num_dashes=60))
    name = Text(title, font_size=18, color=FOREST, weight=BOLD)
    return VGroup(name, VGroup(*parts)).arrange(DOWN, buff=0.1)


def _tick(x, y):
    """A tick mark in a box whose centre is (x, y)."""
    return polyline([(x - 0.13, y - 0.01, 0), (x - 0.04, y - 0.12, 0), (x + 0.15, y + 0.14, 0)], color=FOREST, stroke_width=6)


def _panel():
    """A real solar panel, drawn as a frame with a grid of cells."""
    frame = RoundedRectangle(corner_radius=0.15, width=3.0, height=2.0, stroke_color=MID, stroke_width=4,
                             fill_color=WHITE, fill_opacity=1)
    cells = VGroup(*[Square(0.48, fill_color=LIGHT, fill_opacity=0.9, stroke_width=0) for _ in range(8)])
    cells.arrange_in_grid(rows=2, cols=4, buff=0.12).move_to(frame)
    return VGroup(frame, cells)


class Limits(Narrated):
    scene_id = "limits"

    def construct(self):
        n = self.n
        self.header()
        day = pvdata.day()
        daylight = day.predicted >= 5                       # the app's power floor (POWER_FLOOR_W)
        signed = day.deviation[daylight]
        size = np.abs(signed)                               # the app's limits use the size of the deviation
        mu, sigma = size.mean(), size.std()
        warn, abn = mu + 2 * sigma, mu + 3 * sigma
        rng = np.random.default_rng(7)

        # beat 0: where the limits sit on the deviation axis
        axis = Line([-6.3, AX_Y, 0], [6.3, AX_Y, 0], color=MUTE, stroke_width=3)
        ticks = VGroup()
        for v in (-40, -20, 0, 20, 40):
            x = v * SC
            ticks.add(Line([x, AX_Y, 0], [x, AX_Y - 0.12, 0], color=MUTE, stroke_width=3),
                      Text(str(v), font_size=20, color=MUTE).move_to([x, AX_Y - 0.42, 0]))
        axis_title = Text("power deviation (%)", font_size=22, color=INK).move_to([0, AX_Y - 0.9, 0])
        cloud = _dots(signed, AX_Y + 0.15, 0.9, MID, rng)                  # the healthy day, real samples
        fault_day = pvdata.day(pvdata.FaultKind.PARTIAL_SHADING)
        after = (fault_day.hours >= 11.5) & (fault_day.predicted >= 5)
        faults = _dots(fault_day.deviation[after], AX_Y + 0.15, 0.9, OLIVE, rng)  # a real fault, after it starts
        tight = VGroup(*[Line([s * SC, AX_Y, 0], [s * SC, AX_Y + 2.0, 0], color=OLIVE, stroke_width=5) for s in (-1, 1)])
        loose = VGroup(*[DashedLine([s * 40 * SC, AX_Y, 0], [s * 40 * SC, AX_Y + 2.0, 0], color=OLIVE, stroke_width=5,
                                    dash_length=0.14) for s in (-1, 1)])
        false_label = Text("false alarms", font_size=24, color=OLIVE, weight=BOLD).move_to([0, AX_Y + 2.5, 0])
        missed_label = Text("missed fault", font_size=24, color=OLIVE, weight=BOLD).move_to(
            [float(fault_day.deviation[after].mean()) * SC, AX_Y + 2.5, 0])
        beat0 = VGroup(axis, ticks, axis_title, cloud, faults, tight, loose, false_label, missed_label)

        self.at(n.start(0), FadeIn(axis, ticks, axis_title), FadeIn(cloud), FadeIn(faults))
        self.at(n.cue(0, "tight"), Create(tight), FadeIn(false_label))
        self.at(n.cue(0, "loose"), Create(loose))
        self.at(n.cue(0, "slip"), FadeIn(missed_label))

        # beat 1: the histogram of the healthy day, with the mean and the two limits
        counts, edges = np.histogram(size, bins=np.arange(0, 2.25, 0.25))   # 0.25 % bins
        hyscale = 2.5 / counts.max()
        bars, tails = VGroup(), VGroup()
        for lo, hi, c in zip(edges[:-1], edges[1:], counts):
            if c == 0:
                continue
            h = c * hyscale
            bars.add(Rectangle(width=(hi - lo) * HSC, height=h, fill_color=LIGHT, fill_opacity=1, stroke_color=BG,
                               stroke_width=1).move_to([_hx((lo + hi) / 2), HB + h / 2, 0]))
            if hi > warn:                                             # the part beyond the warning limit
                x0 = max(lo, warn)
                tails.add(Rectangle(width=(hi - x0) * HSC, height=h, fill_color=OLIVE, fill_opacity=1, stroke_width=0)
                          .move_to([_hx((x0 + hi) / 2), HB + h / 2, 0]))
        hist_axis = Line([_hx(0) - 0.2, HB, 0], [_hx(2.0) + 0.2, HB, 0], color=MUTE, stroke_width=3)
        hist_ticks = VGroup()
        for v in (0, 0.5, 1, 1.5, 2):
            x = _hx(v)
            hist_ticks.add(Line([x, HB, 0], [x, HB - 0.12, 0], color=MUTE, stroke_width=3),
                           Text(f"{v:g}", font_size=20, color=MUTE).move_to([x, HB - 0.42, 0]))
        hist_title = Text("size of the daylight deviation (%)", font_size=22, color=INK).move_to([_hx(1.0), HB - 0.9, 0])

        def vline(v, top, color, width=4):
            return Line([_hx(v), HB, 0], [_hx(v), HB + top, 0], color=color, stroke_width=width)

        mean_line, warn_line, abn_line = vline(mu, 2.95, FOREST), vline(warn, 3.4, OLIVE, 5), vline(abn, 2.95, OLIVE, 5)
        mean_lab = Text("mean", font_size=22, color=FOREST, weight=BOLD).next_to(mean_line, UP, buff=0.08)
        warn_lab = Text("+2 σ", font_size=22, color=OLIVE, weight=BOLD).next_to(warn_line, UP, buff=0.08)
        abn_lab = Text("+3 σ", font_size=22, color=OLIVE, weight=BOLD).next_to(abn_line, UP, buff=0.08)
        hist_base = VGroup(bars, hist_axis, hist_ticks, hist_title)
        hist = VGroup(hist_base, mean_line, warn_line, abn_line, mean_lab, warn_lab, abn_lab)

        pill_warn = pill("warning limit 1.2 %", color=MID, size=22).move_to([4.6, 1.55, 0])
        pill_tail = pill("about 4 % of healthy\nsamples above it", color=OLIVE, size=22).move_to([4.6, 0.55, 0])

        self.at(n.start(1), FadeOut(beat0), FadeIn(hist_base))
        self.at(n.cue(1, "mean"), Create(mean_line), FadeIn(mean_lab))
        self.at(n.cue(1, "two"), Create(warn_line), FadeIn(warn_lab))
        self.at(n.cue(1, "three"), Create(abn_line), FadeIn(abn_lab))

        # beat 2: the right tail beyond the warning limit
        self.at(n.start(2), FadeIn(tails))
        self.at(n.cue(2, "one"), FadeIn(pill_warn))
        self.at(n.cue(2, "four"), FadeIn(pill_tail))
        self.at(n.cue(2, "exceed"), Indicate(tails))

        # beat 3: the trap
        self.at(n.cue(3, "bell"), Indicate(bars))
        trap = callout("Derived limits can raise false alarms:\ncheck them", tag="TRAP", color=OLIVE, size=30)
        self.at(n.cue(3, "trust"), FadeOut(hist, tails, pill_warn, pill_tail), FadeIn(trap))
        self.finish()


class Validation(Narrated):
    scene_id = "validation"

    def construct(self):
        n = self.n
        self.header()
        healthy = pvdata.day(seed=0)
        faults = fault_batch(bundled_run_config(seed=0))     # the app's own validation runs: one hour per fault
        thumbs = [_thumb("healthy", healthy.hours, healthy.measured, healthy.predicted)]
        for run_ in faults:
            hours, measured, predicted = _curves(run_.result.samples)
            thumbs.append(_thumb(run_.kind.value, hours, measured, predicted, fault=True))
        slots = [(-4.4, 1.05), (0.0, 1.05), (4.4, 1.05), (-4.4, -1.35), (0.0, -1.35), (4.4, -1.35)]
        for t, (x, y) in zip(thumbs, slots):
            t.move_to([x, y, 0])
        score = pill("Run validation", color=MID, size=24).move_to([0, -2.6, 0])
        legend = Text("solid: measured     dashed: twin     shaded: one-hour fault", font_size=18, color=MUTE).move_to([0, 2.35, 0])
        beat0 = VGroup(*thumbs, score, legend)

        self.at(n.cue(0, "healthy"), FadeIn(thumbs[0]), FadeIn(legend))
        self.at(n.cue(0, "five"), LaggedStart(*[FadeIn(t) for t in thumbs[1:]], lag_ratio=0.15), run_time=0.9)
        self.at(n.cue(0, "scores"), FadeIn(score))

        # beat 1: open Analysis, press SIMULATION, run validation
        shot1 = shot("simple_14_analysis_empty.png", width=12.6, crop=(0.0, 0.0, 1.0, 0.45)).move_to([0, -0.2, 0])
        sim_box = shot_region(shot1, 0.9122, 0.1085, 0.9852, 0.2016, buff=0.04)
        run_box = shot_region(shot1, 0.8917, 0.3075, 0.9789, 0.4083, buff=0.04)
        self.at(n.start(1), FadeOut(beat0), FadeIn(shot1))
        self.at(n.cue(1, "simulation"), Create(sim_box))
        self.at(n.cue(1, "run"), Create(run_box))
        self.at(n.cue(1, "seconds"), Indicate(run_box))

        # beat 2: the healthy accuracy card (cropped to the cards and tables)
        shot2 = shot("simple_15_analysis_results.png", width=12.0, crop=(0.0, 0.1, 1.0, 0.6)).move_to([0, 0.0, 0])
        # fractions of the cropped 1422 x 1000 image (tutorials/screens/simple_15_analysis_results.png, with its Baseline offset tile)
        card_box = shot_region(shot2, 0.1821, 0.192, 0.5752, 0.390, buff=0.03)
        mae_box = shot_region(shot2, 0.1885, 0.256, 0.2475, 0.370, buff=0.02)
        rmse_box = shot_region(shot2, 0.2869, 0.256, 0.3460, 0.370, buff=0.02)
        mape_box = shot_region(shot2, 0.3853, 0.256, 0.4445, 0.370, buff=0.02)
        baseline_box = shot_region(shot2, 0.4838, 0.256, 0.5506, 0.370, buff=0.02)
        self.at(n.start(2), FadeOut(shot1, sim_box, run_box), FadeIn(shot2))
        self.at(n.cue(2, "M"), Create(card_box))
        self.at(n.cue(2, "zero"), Create(mae_box))
        self.at(n.cue(2, "R"), Create(rmse_box))
        self.at(n.cue(2, "M", nth=2), Create(mape_box))
        self.at(n.cue(2, "baseline"), Create(baseline_box))

        # beat 3: fault detection
        det_box = shot_region(shot2, 0.5865, 0.192, 0.9796, 0.390, buff=0.03)
        each_box = shot_region(shot2, 0.1821, 0.460, 0.5724, 0.932, buff=0.03)
        fa_box = shot_region(shot2, 0.8193, 0.256, 0.8790, 0.370, buff=0.02)
        meandev_box = shot_region(shot2, 0.4860, 0.516, 0.5577, 0.888, buff=0.02)
        self.at(n.cue(3, "detected"), FadeOut(card_box, mae_box, rmse_box, mape_box, baseline_box), Create(det_box))
        self.at(n.cue(3, "delay"), FadeOut(det_box), Create(each_box))
        self.at(n.cue(3, "false"), FadeOut(each_box), Create(fa_box))
        self.at(n.cue(3, "mean"), FadeOut(fa_box), Create(meandev_box))

        # beat 4: twin against truth
        table_box = shot_region(shot2, 0.6034, 0.514, 0.9648, 0.702, buff=0.03)
        healthy_box = shot_region(shot2, 0.6913, 0.578, 0.7820, 0.638, buff=0.02)
        fault_box = shot_region(shot2, 0.8734, 0.64, 0.9649, 0.70, buff=0.02)
        self.at(n.start(4), FadeOut(meandev_box), Create(table_box))
        self.at(n.cue(4, "counts"), Indicate(table_box))
        self.at(n.cue(4, "healthy"), FadeOut(table_box), Create(healthy_box))
        self.at(n.cue(4, "fault"), FadeOut(healthy_box), Create(fault_box))
        self.finish()


class Caution(Narrated):
    scene_id = "caution"

    def construct(self):
        n = self.n
        self.header()
        # beat 0-1: a sudden one-hour step on the left, a gradual ramp on the right (schematic)
        step_ax = small_axes([0, 1], [0, 1], 4.8, 2.6).move_to([-3.9, -0.5, 0])
        step_pts = [(0, 0), (0.3, 0), (0.3, 1), (0.42, 1), (0.42, 0), (1, 0)]
        step = polyline([step_ax.c2p(x, y) for x, y in step_pts], color=OLIVE, stroke_width=6)
        step_name = label("validation", size=26, color=FOREST, weight=BOLD).move_to([-3.9, 1.15, 0])
        pill100 = pill("100 %", color=MID, size=24).move_to([-1.9, 1.15, 0])
        ramp_ax = small_axes([0, 1], [0, 1], 4.8, 2.6).move_to([3.6, -0.5, 0])
        ramp = polyline([ramp_ax.c2p(0, 0), ramp_ax.c2p(1, 0.9)], color=OLIVE, stroke_width=6)
        ramp_name = label("real faults", size=26, color=OLIVE, weight=BOLD).move_to([3.6, 1.15, 0])
        time_step = label("time", size=20, color=MUTE).move_to([-3.9, -2.15, 0])
        time_ramp = label("time", size=20, color=MUTE).move_to([3.6, -2.15, 0])
        plots = VGroup(step_ax, step, step_name, pill100, ramp_ax, ramp, ramp_name, time_step, time_ramp)

        self.at(n.start(0), FadeIn(step_ax, time_step))
        self.at(n.cue(0, "step"), Create(step), FadeIn(step_name))
        self.at(n.cue(0, "perfect"), FadeIn(pill100))
        self.at(n.cue(1, "gradually"), FadeIn(ramp_ax, ramp_name, time_ramp), Create(ramp, rate_func=linear), run_time=1.0)

        # beat 2: the plant and the twin are the same model family
        plant = block("plant", width=2.6, height=1.1, size=30).move_to([-3.0, 0.4, 0])
        twin = block("twin", width=2.6, height=1.1, size=30).move_to([3.0, 0.4, 0])
        equals = tex("=", size=90, color=FOREST).move_to([0, 0.4, 0])
        same = callout("The same model family", tag="CAUTION", color=OLIVE, size=28).move_to([0, -1.5, 0])
        self.at(n.start(2), FadeOut(plots), FadeIn(plant, twin))
        self.at(n.cue(2, "same"), FadeIn(equals), FadeIn(same))
        self.at(n.cue(2, "simulation"), Indicate(twin))
        self.at(n.cue(2, "real"), Indicate(plant))

        # beat 3: real measurements come in through the dataset
        panel = _panel().move_to([-4.2, 0.4, 0])
        panel_name = label("real panel", size=24, color=INK).move_to([-4.2, -0.85, 0])
        twin2 = block("twin", width=2.6, height=1.1, size=30).move_to([3.6, 0.4, 0])
        arrow = flow_arrow([-2.7, 0.4, 0], [2.3, 0.4, 0], width=5)
        dataset = pill("dataset", color=MID, size=24).move_to([-0.2, 1.1, 0])
        self.at(n.start(3), FadeOut(plant, twin, equals, same), FadeIn(panel, panel_name, twin2), run_time=0.6)
        self.at(n.cue(3, "dataset"), Create(arrow), FadeIn(dataset))
        self.at(n.cue(3, "twin"), Indicate(twin2))
        self.finish()


class Path(Narrated):
    scene_id = "path"

    def construct(self):
        n = self.n
        self.header()
        sun = block("sun", width=2.5, height=1.0, size=26).move_to([-5.1, 0.95, 0])
        temp = block("temperature", width=2.5, height=1.0, size=26).move_to([-5.1, -0.95, 0])
        twin = block("twin", width=2.5, height=1.0, size=26).move_to([-1.6, 0, 0])
        dev = block("deviation", width=2.5, height=1.0, size=26).move_to([1.8, 0, 0])
        state = block("state", width=2.5, height=1.0, size=26).move_to([5.1, 0, 0])
        a_sun = flow_arrow(sun.get_right(), twin.get_left())
        a_temp = flow_arrow(temp.get_right(), twin.get_left())
        a_dev_in = flow_arrow(twin.get_right(), dev.get_left())
        a_state = flow_arrow(dev.get_right(), state.get_left())
        flow = VGroup(sun, temp, twin, dev, state, a_sun, a_temp, a_dev_in, a_state)

        self.at(n.cue(0, "sun"), FadeIn(sun), FadeIn(temp))
        self.at(n.cue(0, "twin"), FadeIn(twin), Create(a_sun), Create(a_temp))
        self.at(n.cue(0, "deviation"), FadeIn(dev), Create(a_dev_in))
        self.at(n.cue(0, "limits"), FadeIn(state), Create(a_state))

        # beat 1: a checklist, each line ticked as it is done
        ys = [1.5, 0.3, -0.9, -2.1]
        items = ["Inject each fault and read its fingerprint.", "Import a dataset.",
                 "Compare the derived limits with the defaults.", "Run validation, and read its warning."]
        rows, ticks = [], []
        for y, text in zip(ys, items):
            box = RoundedRectangle(corner_radius=0.06, width=0.42, height=0.42, stroke_color=FOREST, stroke_width=3,
                                   fill_color=WHITE, fill_opacity=1).move_to([-5.2, y, 0])
            rows.append(VGroup(box, Text(text, font_size=28, color=INK).next_to(box, RIGHT, buff=0.35)))
            ticks.append(_tick(-5.2, y))
        checklist = VGroup(*rows, *ticks)

        self.at(n.start(1), FadeOut(flow), run_time=0.6)
        self.at(n.cue(1, "inject"), FadeIn(rows[0]))
        self.at(n.cue(1, "fingerprint"), Create(ticks[0]), run_time=0.4)
        self.at(n.cue(1, "import"), FadeIn(rows[1]))
        self.at(n.cue(1, "dataset"), Create(ticks[1]), run_time=0.4)
        self.at(n.cue(1, "compare"), FadeIn(rows[2]))
        self.at(n.cue(1, "defaults"), Create(ticks[2]), run_time=0.4)
        self.at(n.cue(1, "validation"), FadeIn(rows[3]))
        self.at(n.cue(1, "warning"), Create(ticks[3]), run_time=0.4)

        # beat 2: the end card
        title = Text("PV Digital Twin", font_size=64, color=FOREST, weight=BOLD).move_to([0, 0.9, 0])
        subtitle = label("the simple version manual covers every page", size=30, color=MID).move_to([0, -0.2, 0])
        tutorials = pill("tutorials 1 to 6", color=MID, size=26).move_to([0, -1.3, 0])
        self.at(n.start(2), FadeOut(checklist), run_time=0.3)
        self.at(n.cue(2, "manual"), FadeIn(title), FadeIn(subtitle), FadeIn(tutorials))
        self.at(n.cue(2, "Thank"), Indicate(title))
        self.finish()
