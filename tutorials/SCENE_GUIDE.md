# Scene coding guide (for the agents who write a video's `scenes.py`)

You are given one video folder (`tutorials/<name>/`) and a list of scene classes to write. The narration is
already recorded and timed; your job is the Manim animation that accompanies it. Read this file, then
`STYLE.md`, `common/style.py`, `common/narrated.py`, `common/shots.py`, `common/pvdata.py` and `_template/scenes.py`.

## Your inputs

* `tutorials/<name>/script.json`: for your scenes, each beat has `say` (spoken text) and `visual` (what must appear, and on
  which spoken word: "cue 'word'"). The `visual` notes are the storyboard. Follow them; if something is
  impossible or ugly, do the closest clean thing and say so in your final message.
* `tutorials/<name>/build/timeline.json` and `words.json` already exist (narration is synthesised), so `n.cue(beat, "word")`
  returns real times and you can render drafts.
* Your video's `scenes.py` already holds one stub class per scene (header + finish) with the right class name and `scene_id`.
  Replace each stub's `construct` with the real animation. Keep every class name and `scene_id`. Start the file with `import numpy as np`
  and `from common import *`. Remove nothing from `script.json`; do not touch other videos, `common/`, or git (**never run git commands**).

## Pattern (copy it)

```python
class Heaviside(Narrated):
    scene_id = "heaviside"

    def construct(self):
        n = self.n                      # timing of this scene's narration
        self.header()                   # chapter label, title, progress bar (always first)
        eq = tex_parts(r"\frac{5s+7}{(s+1)(s+3)}", "=", r"\frac{A}{s+1}", "+", r"\frac{B}{s+3}", size=44).set_y(1.4)
        self.at(n.start(1), Write(eq[0]))                       # at the start of beat 1
        self.at(n.cue(1, "write"), FadeIn(eq[1:]))              # exactly when the word 'write' is spoken
        ...
        self.finish()                                           # hold until the scene's slot ends (always last)
```

* `self.at(t, anims..., run_time=0.7)` waits until scene time `t` then plays. `n.start(i)`, `n.end(i)`, `n.cue(i, "word", nth=0)`.
  If a cue word is spoken twice in a beat use `nth=1` for the second. Use only words that really occur in the `say` text.
* Never go backwards in time: successive `self.at` calls must be in non-decreasing time order. If an animation is
  longer than the gap to the next cue the next one starts late: shorten `run_time` instead. Use short run_times
  (0.4 to 0.7 s) for reveals.
* Long simulations: `ValueTracker` + `always_redraw`, then `self.advance(tracker, t)`.
* Real curves come from `common/pvdata.py` (`pvdata.iv`, `pvdata.fault_iv`, `pvdata.day`, `pvdata.module`: the app's own engine) and are drawn with `trace(ax, xs, ys)` or `ax.plot`. Never hand-draw a curve that the engine can compute.
  To draw a curve over time use `Create(curve, run_time=..., rate_func=linear)`.
* Maths: `MathTex` via `tex(...)` / `tex_parts(...)`. Pieces from `tex_parts` can be coloured: `eq[2].set_color(LIME)`.
  Plain text labels: `Text` via `label(...)` (never smaller than 15 pt). Mixed text and maths in one line is hard:
  put them side by side with `VGroup(...).arrange(RIGHT)`.
* `MathTex` pitfalls: a raw string `r"..."` always; `\text{...}` for words; `\cancel` needs `\usepackage{cancel}`: avoid it, draw a `Line`
  or `Cross` instead; indexing `eq[0][3:6]` selects glyphs inside a piece and is fragile, prefer splitting into pieces.

## Layout rules (these caused most rework in chapter 1)

* Frame 14.22 x 8. Header above y = 2.9 (drawn by `self.header()`). **Content between y = -3.0 and y = 2.9.** Captions burn in below
  -3.0: nothing may enter that zone (a countdown bar at y = -2.75 is the one exception).
* Keep margins: x between -6.6 and 6.6. Use `.set_y`, `.to_edge`, `arrange` instead of guessing; check `mob.get_bottom()[1] > -3.0`.
* **No text on top of lines, curves, arrows or other text.** Put labels beside objects with `next_to(..., buff=0.15)`.
* Formulas at most about 11 units wide; if wider, split over two lines. Font sizes: formulas 36 to 54, labels 20 to 26.
* Colours only from `style.py` (greens). LIME = look here: use it for **boxes, dots, lines, fills, borders only**. It is too faint as
  text on the pale background: emphasised text and result numbers are FOREST (bold) or OLIVE. OLIVE = problem, trap, disturbance. MUTE = axes.
* **Use the frame.** Main formulas font_size 54 to 60, supporting lines 40 to 48, labels 22 to 26. Centre the composition in the content
  zone (about -2.8 to 2.6); do not leave the lower half empty while the top is crammed. Two-column layouts: left x about -3.5, right x about +3.5.
* `SPlane`: keep poles at least 1 unit inside the plane's border (choose y_range generously, e.g. +-4.5 for poles at +-3j).
* Keep the same object in the same place across beats; reveal rather than redraw. When a new idea needs room, fade out the old one.
* A scene must not be empty for more than about 4 seconds: if the voice is explaining, something small should move (highlight with
  `Indicate`, `Circumscribe`, `ShowPassingFlash`, a colour change).

## Checking your work (you must do all of it)

```bash
cd <repo>
python3 tutorials/check.py tutorials/<name>                 # script and wiring: must be 0 errors
python3 tutorials/check.py tutorials/<name> --cues          # every literal cue word is really spoken: fix any warning for your classes
tutorials/.venv/bin/python tutorials/common/render.py tutorials/<name> --scenes MyClass --quality l      # draft of one scene, about 20 to 60 s
```

Then LOOK at frames: the draft is `tutorials/<name>/build/clips_480p15/<scene_id>.mp4` (plus the whole thing in `build/tutorial_480p15.mp4`
if all scenes are rendered). Extract frames with
`ffmpeg -v error -y -ss <seconds> -i tutorials/<name>/build/clips_480p15/<scene_id>.mp4 -frames:v 1 /tmp/<scene_id>_<t>.png`
and open them with the Read tool. Check at least the middle and the end of every beat: nothing overlapping, nothing below y = -3.0,
nothing cut at the sides, the right object visible when the word is spoken. Fix what you see. Only render your own scenes, one at
a time (the machine is shared).

## Done means

* every class in your file renders without errors at `--quality l`;
* `check.py` has 0 errors and no cue warning for your classes;
* you looked at frames of every beat and fixed overlaps, clipping, caption-zone intrusions;
* the maths on screen matches `script.json` exactly (you do not change the numbers);
* final message: the file name, the classes done, anything you could not do or are unsure about (be honest; do not claim to have
  checked something you did not).


## This project's helpers (read before coding)

* `pvdata` (already imported by `from common import *`): `pvdata.iv(g, t)` returns an `IVCurve` with `.voltage`, `.current`, `.power`,
  `.mpp_voltage`, `.mpp_current`, `.mpp_power`. `pvdata.fault_iv(pvdata.FaultKind.PARTIAL_SHADING)` returns `(healthy, faulty)` curves.
  `pvdata.day(fault=None, fault_hour=11.0)` returns a `DayData` with numpy arrays `hours`, `measured`, `predicted`, `deviation`, a list `state`,
  `irradiance`, `temperature`, `voltage`, `current`. Run `tutorials/.venv/bin/python -W ignore tutorials/common/pvdata.py` to see typical values.
* `shot(name, width, crop=None)` puts a screenshot from `docs/screenshots/` on screen (a Group of image and frame; use `.image` for the
  image itself). `shot_region(group, fx0, fy0, fx1, fy1)` returns a lime box round part of it, in fractions of the image (0, 0 is top left).
  **Look at the screenshot with the Read tool first** and measure the fractions; do not guess. Screenshots are 1400 px wide, so text in
  them is small: crop to the part you talk about (`crop=`) and make it big, or box it. Use `FadeIn(group)` not `Write`.
  Image mobjects fade with `FadeIn`/`FadeOut` and move with `.animate`; do not call `set_color` on them.
* `ImageMobject` cannot be inside a `VGroup`: use `Group` (which `shot` already returns).
* Narration speaks numbers as words, so cue on the spoken word (`"thirty"`, `"eight"`), never on a digit. `"say"` is the spoken text; the caption
  may differ. Cue words must be spoken exactly in the beat (the lint lists any that are not).
* The voice is slow and clear (speed 0.92); beats are 15 to 35 words. Do not make visuals rush: one reveal per spoken idea.
* Colour meaning in this series: **forest / mid green** = the twin and structure, **black (INK)** = measured / the plant, **olive** = fault, trap or
  problem, **lime** = look here (boxes, dots, fills only). Predicted power is always mid green dashes, measured power always INK.
