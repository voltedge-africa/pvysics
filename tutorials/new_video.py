#!/usr/bin/env python3
"""Create a new video folder from the template.

  python3 tutorials/new_video.py ch02-modelling "Mathematical modelling"

Creates tutorials/ch02-modelling/{script.json,scenes.py}; nothing is rendered or synthesised.
"""
import re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if len(sys.argv) != 3 or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sys.argv[1]):
    sys.exit('usage: new_video.py <folder-name, lowercase-with-dashes> "<title>"')
name, title = sys.argv[1], sys.argv[2]
dest = ROOT / name
if dest.exists():
    sys.exit(f"{dest} already exists")
shutil.copytree(ROOT / "_template", dest)
for f in dest.iterdir():
    f.write_text(f.read_text().replace("{{TITLE}}", title))
print(f"created tutorials/{name}/\n"
      f"  1. write the narration in tutorials/{name}/script.json and the scenes in scenes.py\n"
      f"  2. bash tutorials/build.sh {name} --draft     # quick 480p check\n"
      f"  3. bash tutorials/build.sh {name}             # final 1080p -> tutorials/out/{name}.mp4")
