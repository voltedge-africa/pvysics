# Worker brief (scene-coding agents)

Give this file to a worker with the video folder name, e.g. "Your VIDEO is t01-the-big-idea". Replace VIDEO below with that name.

You are a Manim scene-coding worker. Repository: /home/sipho/Documents/Zwane (work from this directory; use absolute or repo-relative paths).

TASK: write the animation for ONE tutorial video of the "PV Digital Twin" tutorial series, in `tutorials/VIDEO/scenes.py`.
The narration is already recorded and timed; you write the Manim scenes that accompany it, cued to the spoken words.

READ FIRST, in this order (all under tutorials/): SCENE_GUIDE.md (your rules; follow it exactly, including "Done means"),
STYLE.md, common/style.py, common/narrated.py, common/shots.py, common/pvdata.py, _template/scenes.py, and your video's script.json.
In script.json each beat has `say` (spoken text), optionally `cap` (caption), and `visual` (the storyboard: what must appear, and on which
spoken word "cue 'word'"). Follow the storyboard. If something is impossible or ugly, do the closest clean thing and say so in your final message.

YOUR FILE: tutorials/VIDEO/scenes.py already has one stub class per scene (right class name and scene_id). Replace each stub with the real
scene. Keep every class name and scene_id. Do not edit script.json, common/, other videos' folders, or anything outside your video folder.
NEVER run git commands.

PROJECT FACTS: the video explains a desktop app (a PV digital twin). Screenshots of the real app are in docs/screenshots/ and are used through
`shot(...)` (see common/shots.py). LOOK at each screenshot you use with the Read tool before placing boxes on it (they are 1400 px wide). Curves
must come from `pvdata` (the app's own engine), never hand-drawn. Colours: greens only (style.py); INK = measured/plant, mid green dashes =
predicted/twin, olive = fault or trap, lime = boxes/dots only (never thin text).

NUMBERS: do not change any number in the narration or storyboard. Typeset maths with MathTex through `tex()` / `tex_parts()`; if a LaTeX
construct fails, simplify it rather than leaving the scene broken.

CHECK YOUR WORK (all of it, in this order):
  python3 tutorials/check.py tutorials/VIDEO                 # must be 0 errors
  python3 tutorials/check.py tutorials/VIDEO --cues          # no cue warnings for your classes
  tutorials/.venv/bin/python -W ignore tutorials/common/render.py tutorials/VIDEO --scenes ClassName --quality l    # one scene at a time
Draft clips appear in tutorials/VIDEO/build/clips_480p15/<scene_id>.mp4. Extract frames with
  ffmpeg -v error -y -ss <seconds> -i tutorials/VIDEO/build/clips_480p15/<scene_id>.mp4 -frames:v 1 /tmp/VIDEO_<scene_id>_<t>.png
and LOOK at them with the Read tool: at least the middle and end of every beat. Fix overlapping text, anything below y = -3.0 (caption zone),
anything clipped at the sides, a wrong object visible when a word is spoken. Render only your own scenes, one at a time (the machine is shared with
five other workers). Finally render ALL your scenes once (omit --scenes) to confirm none crash.

Be careful with: `ImageMobject` inside `Group` (not VGroup); successive `self.at(...)` calls must be in non-decreasing time order; never leave a scene
empty for more than ~4 seconds (add a small Indicate/Circumscribe/colour change); use the frame (large maths 44-60 pt, labels 22-26 pt).

FINAL MESSAGE: the file name, which scenes you finished, what you checked by looking at frames (be specific), and anything you could not do or
are unsure about. Be honest: do not claim to have checked something you did not.
