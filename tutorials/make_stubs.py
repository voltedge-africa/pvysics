#!/usr/bin/env python3
"""Write a stub scenes.py (header + finish) for every video that has none, from its script.json.

    python3 tutorials/make_stubs.py            # skips videos that already have a scenes.py
"""
import json
from pathlib import Path

for script_path in sorted(Path(__file__).resolve().parent.glob("t*/script.json")):
    target = script_path.parent / "scenes.py"
    if target.exists():
        continue
    script = json.loads(script_path.read_text())
    lines = [f'"""{script["title"]}: scenes (stubs; the Manim animation of each scene is written against the storyboard in script.json)."""',
             "import numpy as np", "", "from common import *", ""]
    for sc in script["scenes"]:
        lines += ["", f"class {sc['class']}(Narrated):", f'    scene_id = "{sc["id"]}"', "", "    def construct(self):",
                  "        self.header()", "        self.finish()", ""]
    target.write_text("\n".join(lines))
    print("stubs:", target.parent.name)
