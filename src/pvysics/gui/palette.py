"""The light and dark colour palettes, as plain data. No Qt imports: the contrast rules are tested headless.

A Palette is the one place the look of a theme is defined. The Qt layer (gui/theme.py) turns it into a
QPalette and applies it to charts; the design images (gui/model_view.py) are recoloured from it.
The state colours (green, amber, red) are shared by both themes, so a state reads the same on either.
"""

from dataclasses import dataclass

from pvysics.run import State

CHOICE_SYSTEM = "system"  # follow the operating system's light or dark setting
CHOICE_LIGHT = "light"
CHOICE_DARK = "dark"
CHOICES = (CHOICE_SYSTEM, CHOICE_LIGHT, CHOICE_DARK)

STATE_COLOURS = {State.NORMAL: "#2e7d32", State.WARNING: "#f2a900", State.ABNORMAL: "#c62828"}
STATE_TEXT_COLOURS = {State.NORMAL: "#ffffff", State.WARNING: "#000000", State.ABNORMAL: "#ffffff"}


@dataclass(frozen=True)
class Palette:
    """Every colour a theme needs, as "#rrggbb" strings."""

    name: str
    window: str  # window and panel background
    base: str  # list, table and text-entry background
    text: str  # text on window and base
    muted_text: str  # secondary text, such as acknowledged alarms
    highlight: str  # selection and the checked menu item
    highlight_text: str
    link: str
    warning: str  # warning messages on the window, such as warning log lines
    error: str  # error messages on the window
    card: str  # the background behind the schematic and the equations
    card_border: str
    chart_background: str
    chart_foreground: str  # axes, tick labels, axis titles and legend text
    measured: str  # plant power, P measured
    predicted: str  # twin power, P predicted (dashed)
    deviation: str
    irradiance: str
    temperature: str
    voltage: str  # the measured module voltage V
    current: str  # the measured module current I
    model_iv: str  # the model's I-V curve
    model_pv: str  # the model's P-V curve
    operating_point: str  # the measured operating point on the model curves
    schematic_accent: str  # the green component colour in the circuit schematic


# The chrome and the data are green, black, gray and white (the department's colours). Amber and red appear
# only where they carry meaning: the Warning and Abnormal states, alarms and error text.
LIGHT = Palette(
    name="light",
    window="#f3f4f6",
    base="#ffffff",
    text="#1e1e1e",
    muted_text="#5f5f5f",
    highlight="#137f36",
    highlight_text="#ffffff",
    link="#0b5a25",
    warning="#8a5a00",
    error="#c62828",
    card="#ffffff",
    card_border="#d3d7de",
    chart_background="#f3f4f6",
    chart_foreground="#212121",
    measured="#1e1e1e",
    predicted="#137f36",
    deviation="#424242",
    irradiance="#137f36",
    temperature="#616161",
    voltage="#137f36",
    current="#424242",
    model_iv="#1e1e1e",
    model_pv="#616161",
    operating_point="#137f36",
    schematic_accent="#137f36",
)

DARK = Palette(
    name="dark",
    window="#2b2b2b",
    base="#1e1e1e",
    text="#e6e6e6",
    muted_text="#a6a6a6",
    highlight="#1f8a41",
    highlight_text="#ffffff",
    link="#7bd88f",
    warning="#ffca28",
    error="#ff8a80",
    card="#3a3a3a",
    card_border="#5c5c5c",
    chart_background="#2b2b2b",
    chart_foreground="#e0e0e0",
    measured="#f2f2f2",
    predicted="#5bd17a",
    deviation="#d0d0d0",
    irradiance="#5bd17a",
    temperature="#a6a6a6",
    voltage="#5bd17a",
    current="#d0d0d0",
    model_iv="#f2f2f2",
    model_pv="#a6a6a6",
    operating_point="#5bd17a",
    schematic_accent="#81c784",
)


def palette_for(choice: str, system_is_dark: bool) -> Palette:
    """The palette a theme choice gives. System follows the operating system's setting."""
    if choice == CHOICE_LIGHT:
        return LIGHT
    if choice == CHOICE_DARK:
        return DARK
    if choice == CHOICE_SYSTEM:
        return DARK if system_is_dark else LIGHT
    raise ValueError(f"unknown theme choice {choice!r}")


def relative_luminance(colour: str) -> float:
    """WCAG 2 relative luminance of a "#rrggbb" colour, from 0 (black) to 1 (white)."""
    channels = []
    for start in (1, 3, 5):
        value = int(colour[start : start + 2], 16) / 255
        channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """WCAG 2 contrast ratio of two "#rrggbb" colours, from 1 (no contrast) to 21 (black on white)."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
