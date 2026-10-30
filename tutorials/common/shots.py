"""Screenshots of the real app inside scenes (docs/screenshots), with a frame and helpers to point at parts of them.

    g = shot("simple_06_dashboard_fault.png", width=9)           # Group(image, frame); place it like any mobject
    box = shot_region(g, 0.78, 0.28, 1.0, 0.98)                  # a lime box round a region, in fractions of the image
    crop = shot("simple_02_dashboard_normal.png", width=6, crop=(0.0, 0.15, 1.0, 0.30))   # only that band of the image
"""
from pathlib import Path

import numpy as np
from manim import *
from PIL import Image

from .style import *

REPO = Path(__file__).resolve().parents[2]
SHOTS = REPO / "docs" / "screenshots"
# The scenes box regions of these images by fraction, so the exact images they were measured on are frozen in tutorials/screens
# (screenshots in docs/ are refreshed as the app changes). A name found there wins; anything else comes from docs/screenshots.
FROZEN = Path(__file__).resolve().parents[1] / "screens"


def _path(name):
    return FROZEN / name if (FROZEN / name).exists() else SHOTS / name


def shot(name, width=8.0, crop=None, frame=True):
    """A screenshot as a mobject `width` Manim units wide. crop = (x0, y0, x1, y1) in fractions of the image (0 is top left)."""
    img = Image.open(_path(name)).convert("RGB")
    if crop:
        w, h = img.size
        x0, y0, x1, y1 = crop
        img = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    mob = ImageMobject(np.array(img))
    mob.set_height(width * img.size[1] / img.size[0])
    mob.set_width(width)
    border = Rectangle(width=mob.width, height=mob.height, stroke_color=PALE, stroke_width=3, fill_opacity=0).move_to(mob)
    group = Group(mob, border) if frame else Group(mob)
    group.image, group.border = mob, border
    return group


def shot_region(group, fx0, fy0, fx1, fy1, color=LIME, buff=0.0):
    """A box round part of a screenshot shown by `shot`, given in fractions of that image (0, 0 is its top left)."""
    img = group.image
    left, top = img.get_left()[0], img.get_top()[1]
    box = Rectangle(width=(fx1 - fx0) * img.width + 2 * buff, height=(fy1 - fy0) * img.height + 2 * buff,
                    stroke_color=color, stroke_width=5, fill_opacity=0)
    box.move_to([left + (fx0 + fx1) / 2 * img.width, top - (fy0 + fy1) / 2 * img.height, 0])
    return box
