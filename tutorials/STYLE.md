# Style guide

Lessons from the chapter 1 video, so the next ones need less rework.

## Writing the narration (`script.json`)

* **One idea per beat**, ideally 15 to 35 words. Long beats make the visuals hard to follow (the linter warns above 45).
* **Say numbers as words** ("twenty two", "one hundred kilometres per hour") and put the symbols in `"cap"`
  if the caption should show them ("22 °C"). The voice reads `%`, `=`, `/` and digits unpredictably.
* **Acronyms:** if the voice garbles one, spell it in `say` ("P L C") and keep the real form in `cap` ("PLC").
* **Sound like speech**, not a slide: short sentences, "so", "now", "watch what happens".
* **Pauses for the viewer:** `"after": 4.0` on a beat adds that many seconds of silence (used for the
  pause-and-answer quiz in chapter 1). Show a countdown during it.
* **Pick cue words** that the narrator says exactly once in a beat; they drive the animation timing.
* The caption shows `cap` if present, otherwise `say`.

## Cueing visuals

* `n.start(i)` and `n.end(i)` are beat boundaries; `n.cue(i, "word", nth=0)` is the moment a word is
  spoken. All are in scene time. `self.at(t, anim...)` waits until `t`, then plays.
* Long-running simulations: use a `ValueTracker` plus `always_redraw`, then `self.advance(tracker, t)`
  to let it run until each cue.
* A scene must never run shorter than its narration: finish with `self.finish()`.
* `python3 tutorials/check.py <video> --cues` lists any cue word that is not actually spoken (it would
  silently fall back to the beat start).

## Layout

The frame is 14.22 by 8 Manim units. Keep to the zones in `common/style.py`:

| Zone | y range | Contents |
|---|---|---|
| header | above 2.9 | chapter label, scene title, progress bar (`self.header()`) |
| content | -3.0 to 2.9 | everything you draw |
| captions | below -3.0 | karaoke captions burned in at the end; keep it free |

Keep the same positions across scenes where an idea carries over, and avoid text over lines (the
chapter 1 fixes were mostly labels colliding with wires).

## Look

* Shades of green only (palette in `style.py`: `FOREST MID LIGHT PALE`, accent `LIME`, warning `OLIVE`,
  neutral `MUTE`, text `INK`). Lime marks "look here"; olive marks problems or disturbances.
* Font: Liberation Sans (set globally). Titles bold, labels 15 to 24 pt, nothing smaller than 15 pt.
* Reuse `block`, `pill`, `card`, `small_axes`, `polyline`, `label`; add new shared helpers to `common/style.py`.
* Same signal means the same colour in every video (error and signals lime, disturbances olive).

## Pipeline notes

* Scenes render in parallel, each in its own media folder (Manim's text cache is not safe to share).
* `Text` drops whitespace from its glyph list; use `part(text_mobject, "substring")` to colour or box part of a line.
* LaTeX is installed, so formulas can use `MathTex(r"G(s)=\frac{Y(s)}{U(s)}")`. Use `Text` with Unicode (°, ∫) only for tiny inline symbols in labels. Colour parts of a formula with `substrings_to_isolate` / `set_color_by_tex`, and keep formulas inside the content zone.
* Transitions are a short dip to the background colour added at assembly, not something a scene draws.

## Shared helpers for maths and diagrams (`common/style.py`, `common/lti.py`)

* `tex(s)` / `tex_parts(a, b, c)[i]`: MathTex in house colours; build a formula from pieces to reveal or colour one piece.
* `tf_block(r"\frac{1}{s+1}")`, `flow_arrow(a, b)`, `summing_junction()`: block diagrams with typeset transfer functions.
* `SPlane(x_range, y_range, width, height)`: the s-plane. `sp.pole(x, y)` cross, `sp.zero(x, y)` circle, `sp.c2p(x, y)`, `sp.ax`.
* `tex_table(rows, col_w, row_h)`: grid of MathTex cells; `table.cells[r][c]` reveals a table cell by cell (Routh arrays, tuning tables).
* `callout("text\nwraps", tag="EXAM TIP")`, `highlight_box(mob)`, `trace(ax, xs, ys)`.
* `self.countdown(until)` in a scene: the shrinking bar for pause-and-try.
* `lti`: `step`, `impulse`, `second_order(wn, zeta)`, `feedback`, `pid_loop`, `fopdt_pi_step`, `locus_branches`. Animate real responses, not hand-drawn curves.
* A video may split its scenes over several `scenes*.py` files (each starts with `from common import *`).

## Lessons from chapter 2

* LIME is for boxes, dots, lines and fills; as thin text on the pale background it is hard to read. Use FOREST bold or OLIVE for emphasised text.
* Make maths big (54 to 60 pt main line); first drafts left the frame half empty.
* Per-scene `scenes_*.py` files let several agents work in parallel; `render.py` finds each class's file.
* Draw the s-plane with generous ranges so poles do not touch its border.

## Lessons from chapters 2 to 5 (production with scene-coding agents)

* **Cue words are the *spoken* words.** `n.cue(beat, "word")` looks at the `say` text first (with accurate ASR times), then at the caption
  (`cap`) tokens. Numbers and symbols are spoken as words ("minus", "zero"), so cue on those words, not on "−" or "0".
  Spelled acronyms are separate words ("P I D": cue on "P", not "PID").
* Write `script.json` first, run TTS and ASR (`tts.mjs`, `asr.mjs`), *then* code the scenes: durations and cue times are then real.
  Re-synthesis is cached per sentence, so a one-beat narration edit is cheap.
* Put a `"visual"` note on every beat of `script.json` (the storyboard that scene-coding agents are briefed from, see `SCENE_GUIDE.md`).
* Split scenes over `scenes_a.py` .. `scenes_d.py` so agents can work in parallel; `check.py` and `render.py` read all `scenes*.py`.
* Real simulations beat hand-drawn curves: every plot of a response, a locus or an overshoot comes from `common/lti.py`, so the
  numbers on screen are computed, and narration numbers were checked against them (the Ziegler-Nichols example overshoots by 61.8%, 18.6%, 28.1%).
* Equal axis scale matters when angles are shown (damping ray, asymptotes, the angle condition): use an `SPlane` whose width:height equals the data ratio.
* One long beat is hard to follow: keep beats under about 45 words (exam questions are the usual exception).
* Machine load: Manim 1080p builds with eight agents rendering at once take 10 to 20 minutes per video; run builds one or two at a time.
- `formula_card(title, lines, width, size)`: cheat-sheet card with MathTex lines (`card.lines[i]`) for recap videos.
