#!/usr/bin/env python3
"""Recreate tutorials/screens/ (not tracked: it is images): the exact screenshots the scenes box by fraction.

    python3 tutorials/screens.py

Most are the screenshots as committed in 945c920 (Version 0.3.0), read from git. Two are newer and come from docs/screenshots as they
are in your working copy: simple_01b_dashboard_idle_8pages.png (the sidebar with the Live Feed page) and simple_15_analysis_results.png
(with the Baseline offset tile and the Mean deviation column). If you retake those two, re-measure the boxes that use them in
t04-using-the-app/scenes.py (Open) and t06-limits-and-trust/scenes.py (Validation) before building.
"""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "screens"
FROZEN_AT = "945c920"
OUT.mkdir(exist_ok=True)
names = subprocess.run(["git", "ls-tree", "--name-only", FROZEN_AT, "docs/screenshots/"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
count = 0
for name in names:
    base = Path(name).name
    if base.startswith(("simple_", "light_17", "dark_20", "light_20")):
        (OUT / base).write_bytes(subprocess.run(["git", "show", f"{FROZEN_AT}:{name}"], cwd=ROOT, capture_output=True, check=True).stdout)
        count += 1
shutil.copy(ROOT / "docs/screenshots/simple_01_dashboard_idle.png", OUT / "simple_01b_dashboard_idle_8pages.png")
shutil.copy(ROOT / "docs/screenshots/simple_15_analysis_results.png", OUT / "simple_15_analysis_results.png")
print(f"{count} screenshots from {FROZEN_AT} and 2 newer ones written to {OUT}")
