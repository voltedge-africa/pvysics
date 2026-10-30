"""Base class for narrated scenes: wait for spoken words, header, progress bar."""
import os
from pathlib import Path

from manim import *

from .narration import Narration
from .style import *


class Narrated(Scene):
    scene_id = ""

    def setup(self):
        self.n = Narration(self.scene_id, Path(os.environ["VIDEO_DIR"]) / "build")

    # -- timing helpers ---------------------------------------------------------------
    def wait_until(self, t: float):
        if t - self.time > 1e-3:
            self.wait(t - self.time)

    def at(self, t: float, *anims, run_time: float = 0.7, **kw):
        """Wait until scene time `t`, then play `anims`."""
        self.wait_until(t)
        self.play(*anims, run_time=run_time, **kw)

    def advance(self, tracker: ValueTracker, t: float):
        """Let a simulation clock run (value == scene seconds) until scene time `t`."""
        if t - self.time > 1e-3:
            self.play(tracker.animate.set_value(t), run_time=t - self.time, rate_func=linear)

    def header(self):
        # thin progress bar across the top: fraction of the whole video played so far
        bar = always_redraw(lambda: Rectangle(width=max(0.02, config.frame_width * (self.n.origin + self.time) / self.n.total), height=0.07,
                                              fill_color=MID, fill_opacity=1, stroke_width=0).to_corner(UL, buff=0))
        self.add(bar)
        chapter = Text(self.n.label, font_size=15, color=MID, weight=BOLD)
        title = Text(self.n.title, font_size=36, color=FOREST, weight=BOLD)
        group = VGroup(chapter, title).arrange(DOWN, aligned_edge=LEFT, buff=0.08).to_corner(UL, buff=0.45)
        self.play(FadeIn(group, shift=DOWN * 0.15), run_time=0.6)
        return group

    def countdown(self, until: float, y: float = -2.75, width: float = 13.0, text: str = "THINK ABOUT IT…"):
        """A lime bar that shrinks to nothing at scene time `until` (the viewer's thinking time during a quiz pause)."""
        f = ValueTracker(1.0)
        bar = always_redraw(lambda: Rectangle(width=max(0.02, width * f.get_value()), height=0.16, fill_color=LIME, fill_opacity=1,
                                              stroke_width=0).move_to([-width / 2, y, 0], aligned_edge=LEFT))
        think = Text(text, font_size=18, color=OLIVE, weight=BOLD).move_to([-width / 2 + 1.2, y + 0.3, 0])
        self.play(FadeIn(think), run_time=0.3)
        self.add(bar)
        self.play(f.animate.set_value(0), run_time=max(0.5, until - self.time), rate_func=linear)
        self.play(FadeOut(think), FadeOut(bar), run_time=0.3)

    def finish(self):
        self.wait_until(self.n.duration)
