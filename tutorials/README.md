# PV Digital Twin: tutorial series

Seven narrated, animated tutorials that explain, from first principles, how the tool works and how to use it, plus a written
companion handbook. Everything runs locally: Kokoro for the voice, Parakeet for word timings, Manim for the animation, ffmpeg to
assemble, Typst for the handbook and Python for the numbers. Every curve and figure comes from the app's own engine (`src/pvysics`),
and the screenshots are the real app's (`docs/screenshots`).

| # | Video | Teaches |
|---|---|---|
| 1 | `t01-the-big-idea` | Why a power reading means nothing alone; plant, twin, deviation, state, limits, night |
| 2 | `t02-the-twin` | The single diode model from light and a diode; I-V and P-V curves; sun and heat; datasheet to fitted twin |
| 3 | `t03-plant-and-faults` | The plant (mismatch, noise), the five faults and their fingerprints, sensor drift, a fault on a real day |
| 4 | `t04-using-the-app` | A guided tour of every page with screenshots: controls, readings, deviation card, alarms, Trends, Data, Model |
| 5 | `t05-your-own-data` | Dataset analysis: the template, MAE/RMSE/MAPE/MBE worked by hand, replay, weather and datasheet files |
| 6 | `t06-limits-and-trust` | Choosing limits, validation, and what the scores do not say |
| 7 | `t07-live-feed` | Connecting a device: the address and token, what it sends, time and gaps, no-data, the saved file, the limits |

The written companion is `docs/tutorial-handbook.typ` (one chapter per video).

## Build

From the repository root.

    python3 tutorials/series.py                          # (re)write every script.json from the narration and storyboard
    python3 tutorials/make_stubs.py                      # stub scenes.py for a new video
    bash tutorials/build.sh t01-the-big-idea --draft     # 480p check -> tutorials/out/t01-the-big-idea-draft.mp4
    bash tutorials/build.sh t01-the-big-idea             # final 1080p -> tutorials/out/t01-the-big-idea.mp4

    tutorials/.venv/bin/python -W ignore tutorials/figures.py                                   # the handbook figures
    typst compile --root . --font-path src/pvysics/gui/fonts docs/tutorial-handbook.typ docs/tutorial-handbook.pdf

`build.sh` lints the script, synthesises the narration (cached per sentence), gets word timings, checks every cue word was really
spoken, renders the scenes in parallel and assembles the video with burned-in captions. Edit one beat of `series.py` and only that
beat is synthesised again.

## Two voices

| Engine | Voice | Licence | Output |
|---|---|---|---|
| Kokoro (default) | `af_heart`, sherpa-onnx | Apache-2.0: free to share | `tutorials/out/kokoro/` |
| Breeze-TTS-2 | one designed narrator, `zwane-tutor` | research and non-commercial only | `tutorials/out/` |

    python3 tutorials/series.py --engine breeze    # put "engine": "breeze" in every script.json (omit the flag for Kokoro)
    bash tutorials/build.sh t01-the-big-idea       # the engine comes from script.json

Breeze runs locally through the C++/GGUF build `Breeze-TTS-2.cpp` (default `~/Workspace/breeze-cpp`, or set `BREEZE_DIR`) on the GPU
through Vulkan, and needs its saved voice: see `voice/README.md`, which also states the licence. Clips are cached per sentence and per
engine, so switching engines never overwrites the other's audio. The Breeze voice is slower than Kokoro (the series runs about 28 minutes
against 21), and the animation follows the spoken words either way.

## Layout

    tutorials/
      series.py        the narration and the storyboard of every video (the source of every script.json)
      figures.py       SVG figures for the handbook, from the engine
      make_stubs.py    stub scenes for new videos
      build.sh  check.py  new_video.py
      common/
        style.py         palette (greens), layout zones, helpers      narrated.py   the Narrated scene base class
        shots.py         screenshots in scenes: shot(), shot_region()  pvdata.py     real curves and runs from src/pvysics
        tts.mjs asr.mjs  narration and word timings                   captions.py render.py narration.py
      STYLE.md  SCENE_GUIDE.md  WORKER_BRIEF.md     conventions and the brief the scene-coding workers were given
      t01-... t06-.../     one folder per video: script.json, scenes.py, build/ (generated)
      screens/         frozen copies of the screenshots the scenes box by fraction (not tracked: run screens.py to recreate)
      voice/           the Breeze narrator (reference clip, saved voice) and its README
      out/             finished videos (out/kokoro/ holds the Kokoro set)

`build/`, `out/`, `media/` and `.venv/` are generated and git-ignored.

## Setup (once)

    sudo apt install libcairo2-dev libpango1.0-dev pkg-config python3-dev ffmpeg
    uv venv --python 3.12 tutorials/.venv && uv pip install --python tutorials/.venv/bin/python manim

LaTeX is needed for formulas (`texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended dvisvgm`).
The voice and the word timings use the local speech models under `~/.paseo/models` (Kokoro `kokoro-int8-v1_0` and Parakeet) through the
`paseo-tts` plugin's `node_modules` (for `sherpa-onnx-node`), as the paths at the top of `common/tts.mjs` and `common/asr.mjs` show.

## Conventions

Shades of green only; predicted power is always green dashes and measured power always black; olive marks faults and traps; lime marks
"look here". Numbers in the narration are written as words and the symbols go in the caption. See `STYLE.md`.

Scenes measure box positions on the screenshots in `screens/` (images, so not tracked: `python3 tutorials/screens.py` recreates them), which `common/shots.py` prefers over `docs/screenshots/`. When the app
changes and a screenshot is retaken, copy it into `screens/` only after re-measuring the boxes that use it.

The pipeline is adapted from the course-video pipeline in the author's FCNS201 study repository, which is where the conventions in
`STYLE.md` and `SCENE_GUIDE.md` come from.
