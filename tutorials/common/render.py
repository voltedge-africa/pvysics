#!/usr/bin/env python3
"""Render a tutorial video with Manim.

  tutorials/.venv/bin/python tutorials/common/render.py tutorials/<name>                   # -> <name>/build/tutorial.mp4
  tutorials/.venv/bin/python tutorials/common/render.py tutorials/<name> --scenes Hook     # re-render some scenes, re-assemble
  tutorials/.venv/bin/python tutorials/common/render.py tutorials/<name> --quality l       # fast draft (480p15)

Stages: (1) Manim renders each scene of <name>/scenes.py (in parallel); (2) each clip gets its slice of
the narration and a short dip to the background colour at both ends; (3) the clips are joined, karaoke
captions (captions.py, burned in by libass) are added and the audio is loudness-normalised.
Needs <name>/build/{narration.wav,timeline.json,words.json} from tts.mjs and asr.mjs.
"""
import argparse, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # tutorials/
sys.path.insert(0, str(ROOT))
from common import captions  # noqa: E402

BG = "0xf2f8f4"
QUALITY = {"l": ("480p15", "15"), "m": ("720p30", "30"), "h": ("1080p24", "24")}

ap = argparse.ArgumentParser()
ap.add_argument("video", help="the video folder, e.g. tutorials/ch01-introduction")
ap.add_argument("--scenes", default="", help="comma-separated Manim class names (default: all)")
ap.add_argument("--quality", default="h", choices=list(QUALITY))
ap.add_argument("--jobs", type=int, default=4)
a = ap.parse_args()
VIDEO = Path(a.video).resolve()
BUILD = VIDEO / "build"
res, fps = QUALITY[a.quality]
want = set(a.scenes.split(",")) if a.scenes else None

script = json.loads((VIDEO / "script.json").read_text())
CLASSES = {s["id"]: s["class"] for s in script["scenes"]}
tl = json.loads((BUILD / "timeline.json").read_text())
scenes = tl["scenes"]
clips, media = BUILD / f"clips_{res}", BUILD / "media"
clips.mkdir(parents=True, exist_ok=True)
env = {**os.environ, "PYTHONPATH": str(ROOT), "VIDEO_DIR": str(VIDEO)}


def run(cmd, **kw):
    r = subprocess.run(list(map(str, cmd)), capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(map(str, cmd))[:200]}\n{r.stderr[-2500:]}")
    return r


def slot(i):
    origin = 0.0 if i == 0 else scenes[i]["start"]
    end = scenes[i + 1]["start"] if i + 1 < len(scenes) else tl["total"]
    return origin, end - origin


def scenes_file(cls):
    """The scenes*.py file defining `cls` (a video may split its scenes over several files so agents can work in parallel)."""
    for f in sorted(VIDEO.glob("scenes*.py")):
        if f"class {cls}(" in f.read_text():
            return f
    sys.exit(f"class {cls} not found in any scenes*.py of {VIDEO}")


def render(i):
    sc = scenes[i]
    cls = CLASSES[sc["id"]]
    if want and cls not in want:
        return
    origin, dur = slot(i)
    src = scenes_file(cls)
    run([sys.executable, "-m", "manim", f"-q{a.quality}", "--fps", fps, "--media_dir", media / sc["id"], "-o", sc["id"], src, cls], cwd=ROOT, env=env)
    video = next((media / sc["id"]).glob(f"videos/{src.stem}/{res}*/{sc['id']}.mp4"))
    audio = clips / f"{sc['id']}.wav"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{origin:.3f}", "-t", f"{dur:.3f}", "-i", BUILD / "narration.wav", audio])
    fade = f"fade=t=in:st=0:d=0.3:color={BG},fade=t=out:st={dur - 0.3:.3f}:d=0.3:color={BG}"
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", audio, "-vf", fade, "-c:v", "libx264", "-crf", "17", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-r", fps, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", clips / f"{sc['id']}.mp4"])
    print(f"  {cls:14s} {dur:5.1f} s", flush=True)


with ThreadPoolExecutor(max_workers=a.jobs) as ex:
    list(ex.map(render, range(len(scenes))))

listing = BUILD / f"concat_{res}.txt"
listing.write_text("".join(f"file '{clips / (s['id'] + '.mp4')}'\n" for s in scenes))
ass = BUILD / "captions.ass"
print(captions.build(ass, BUILD), "caption events")
out = BUILD / ("tutorial.mp4" if a.quality == "h" else f"tutorial_{res}.mp4")
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing, "-vf", f"subtitles={ass}",
     "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out])
print("wrote", out)
