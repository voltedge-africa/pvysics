"""{{TITLE}}: scenes.

Each scene is a Manim `Scene` that subclasses `Narrated` and sets `scene_id` to a scene id from
script.json (its "class" there must match the class name here). Animations are cued to the
narration:  self.at(n.cue(beat, "word"), FadeIn(thing)).  See video/STYLE.md for conventions.

Draft one scene:  video/.venv/bin/python video/common/render.py video/<name> --scenes Intro --quality l
"""
import numpy as np

from common import *


class Intro(Narrated):
    scene_id = "intro"

    def construct(self):
        n = self.n                       # timing of this scene's narration
        self.header()                    # chapter label, scene title, progress bar
        card_ = card(9, 3).set_y(0.4)
        text = Text("Replace me", font_size=44, color=FOREST, weight=BOLD).move_to(card_)
        ax = small_axes([0, 1], [0, 1], 5, 1.4).move_to(card_.get_bottom() + UP * 0.95)
        curve = ax.plot(lambda x: 0.5 + 0.4 * np.sin(2 * PI * x), x_range=[0, 1, 0.01], color=MID, stroke_width=5)
        self.at(n.start(0), FadeIn(card_), Write(text))                    # when beat 0 starts
        self.at(n.start(1), Create(ax))                                    # when beat 1 starts
        self.play(Create(curve), run_time=3, rate_func=linear)
        self.finish()                                                      # hold until the scene's slot ends


class Outro(Narrated):
    scene_id = "outro"

    def construct(self):
        self.header()
        self.at(self.n.start(0), FadeIn(pill("Thanks for watching", color=MID, size=36).set_y(0.4), shift=UP * 0.3))
        self.finish()
