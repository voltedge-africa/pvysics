"""The stylesheet is built from the palette: headless, no Qt."""

import pytest

import colorsys
from dataclasses import fields

from pvysics.gui.palette import DARK, LIGHT
from pvysics.gui.style import stylesheet


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_the_stylesheet_uses_the_palettes_own_colours(palette):
    sheet = stylesheet(palette)

    for colour in (palette.card, palette.card_border, palette.highlight, palette.muted_text):
        assert colour in sheet


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_the_stylesheet_is_balanced_and_fully_substituted(palette):
    sheet = stylesheet(palette)

    assert sheet.count("{") == sheet.count("}")
    assert "{p." not in sheet and "{{" not in sheet and "}}" not in sheet


def test_an_active_fault_chip_is_the_inverse_of_the_text_colour_in_both_themes():
    for palette in (LIGHT, DARK):
        rule = stylesheet(palette).split('QPushButton[variant="active"] {')[1].split("}")[0]
        assert f"background-color: {palette.text}" in rule and f"color: {palette.window}" in rule


def test_the_two_themes_give_different_sheets():
    assert stylesheet(LIGHT) != stylesheet(DARK)


def _is_blue(colour: str) -> bool:
    red, green, blue = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    hue, saturation, _value = colorsys.rgb_to_hsv(red, green, blue)
    return 0.45 <= hue <= 0.75 and saturation > 0.2  # cyan through blue to violet


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_no_palette_colour_is_blue(palette):
    colours = {f.name: getattr(palette, f.name) for f in fields(palette) if f.name != "name"}

    assert [name for name, colour in colours.items() if _is_blue(colour)] == []
