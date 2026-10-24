from importlib.resources import files

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPalette
from PyQt6.QtWidgets import QApplication

from pvysics.gui import model_view
from pvysics.gui.model_view import ModelView, recoloured_image, recoloured_svg
from pvysics.gui.palette import (
    CHOICE_DARK,
    CHOICE_LIGHT,
    CHOICE_SYSTEM,
    DARK,
    LIGHT,
    STATE_COLOURS,
    STATE_TEXT_COLOURS,
    Palette,
    contrast_ratio,
    palette_for,
)
from pvysics.gui.theme import SETTINGS_KEY, ThemeManager, ThemeMenu, default_settings
from pvysics.run import State
from pvysics.gui.session import Session

PALETTES = [LIGHT, DARK]
WCAG_TEXT_RATIO = 4.5


@pytest.mark.parametrize("palette", PALETTES, ids=lambda palette: palette.name)
def test_text_and_chart_foreground_contrast_exceed_wcag_ratio(palette: Palette):
    assert contrast_ratio(palette.text, palette.window) > WCAG_TEXT_RATIO
    assert contrast_ratio(palette.chart_foreground, palette.chart_background) > WCAG_TEXT_RATIO
    assert contrast_ratio(palette.muted_text, palette.chart_background) > WCAG_TEXT_RATIO  # the axes and tick labels
    assert contrast_ratio(palette.muted_text, palette.window) > WCAG_TEXT_RATIO
    assert contrast_ratio(palette.error, palette.window) > WCAG_TEXT_RATIO


@pytest.mark.parametrize("palette", PALETTES, ids=lambda palette: palette.name)
def test_state_labels_stay_readable_on_their_colour(palette: Palette):
    for state in State:
        assert contrast_ratio(STATE_TEXT_COLOURS[state], STATE_COLOURS[state]) > WCAG_TEXT_RATIO


@pytest.mark.parametrize(
    ("choice", "system_is_dark", "expected"),
    [
        (CHOICE_LIGHT, False, LIGHT),
        (CHOICE_LIGHT, True, LIGHT),
        (CHOICE_DARK, False, DARK),
        (CHOICE_DARK, True, DARK),
        (CHOICE_SYSTEM, False, LIGHT),
        (CHOICE_SYSTEM, True, DARK),
    ],
)
def test_choice_resolves_to_a_palette(choice, system_is_dark, expected):
    assert palette_for(choice, system_is_dark) == expected


def test_unknown_choice_is_rejected():
    with pytest.raises(ValueError):
        palette_for("sepia", system_is_dark=False)


def test_schematic_recolour_drops_the_white_background_and_keeps_green_readable():
    svg = (files("pvysics") / "gui" / "assets" / "circuit_sdm.svg").read_bytes()
    dark = recoloured_svg(svg, DARK).decode("utf-8")

    for original in ("#ffffff", "#000000", "#137f36"):
        assert original not in dark
    assert DARK.window in dark and DARK.text in dark and DARK.schematic_accent in dark
    assert recoloured_svg(svg, LIGHT).decode("utf-8").count(LIGHT.window) >= 1


@pytest.mark.parametrize("name", model_view.EQUATION_IMAGES)
def test_equation_recolour_paints_every_visible_pixel_in_the_ink(name):
    original = QImage()
    assert original.loadFromData((files("pvysics") / "gui" / "assets" / name).read_bytes())
    ink = QColor("#ff0000")
    recoloured = recoloured_image(original, ink)

    assert recoloured.size() == original.size()
    for y in range(0, original.height(), 5):
        for x in range(0, original.width(), 5):
            alpha = original.pixelColor(x, y).alpha()
            pixel = recoloured.pixelColor(x, y)
            assert pixel.alpha() == alpha
            if alpha == 255:
                assert pixel.name() == ink.name()


def test_default_store_is_an_ini_file_under_the_test_directory(qtbot, tmp_path):
    """The app's store is platform-neutral INI, and the test fixture keeps it out of the user's settings."""
    path = default_settings().fileName()

    assert path.endswith(".ini")
    assert path.startswith(str(tmp_path))


def test_system_choice_is_remembered_by_default(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "theme.ini"), QSettings.Format.IniFormat)
    assert ThemeManager(settings).choice == CHOICE_SYSTEM


def test_choice_is_remembered_across_runs(qtbot, tmp_path):
    path = str(tmp_path / "theme.ini")
    ThemeManager(QSettings(path, QSettings.Format.IniFormat)).set_choice(CHOICE_DARK)

    assert ThemeManager(QSettings(path, QSettings.Format.IniFormat)).choice == CHOICE_DARK


def test_unreadable_stored_choice_falls_back_to_system(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "theme.ini"), QSettings.Format.IniFormat)
    settings.setValue(SETTINGS_KEY, "sepia")

    assert ThemeManager(settings).choice == CHOICE_SYSTEM


def test_system_choice_follows_the_os_when_it_changes_at_runtime(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "theme.ini"), QSettings.Format.IniFormat)
    theme = ThemeManager(settings)
    seen = []
    theme.changed.connect(seen.append)

    QGuiApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert theme.palette == DARK
    assert seen == [DARK]

    QGuiApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
    assert theme.palette == LIGHT
    assert seen == [DARK, LIGHT]


def test_manual_choice_ignores_the_os_when_it_changes(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "theme.ini"), QSettings.Format.IniFormat)
    theme = ThemeManager(settings)
    theme.set_choice(CHOICE_LIGHT)
    seen = []
    theme.changed.connect(seen.append)

    QGuiApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)

    assert theme.palette == LIGHT
    assert seen == []


def test_choosing_a_theme_applies_the_palette_to_the_app(qtbot):
    window = Session().open_hmi()
    qtbot.addWidget(window)
    app = QApplication.instance()

    window.theme.set_choice(CHOICE_DARK)
    assert app.palette().color(QPalette.ColorRole.Window) == QColor(DARK.window)
    # With a stylesheet active Qt wraps the style, so its name is empty; the sheet itself follows the theme.
    assert DARK.card_border in app.styleSheet()

    window.theme.set_choice(CHOICE_LIGHT)
    assert app.palette().color(QPalette.ColorRole.Window) == QColor(LIGHT.window)
    assert LIGHT.card_border in app.styleSheet()
    assert DARK.card_border not in app.styleSheet()


def test_view_menus_of_both_windows_stay_in_step(qtbot, tmp_path):
    window = Session(theme=ThemeManager(QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat))).open_hmi()
    qtbot.addWidget(window)
    dashboard = window.open_dashboard()
    hmi_menu, dashboard_menu = window.findChildren(ThemeMenu)[0], dashboard.findChildren(ThemeMenu)[0]

    dashboard_menu.actions[CHOICE_DARK].trigger()

    assert window.theme.choice == CHOICE_DARK
    assert hmi_menu.actions[CHOICE_DARK].isChecked()
    assert not hmi_menu.actions[CHOICE_LIGHT].isChecked()
    assert dashboard_menu.actions[CHOICE_DARK].isChecked()


def test_smoke_switching_theme_with_hmi_and_dashboard_open_recolours_charts(qtbot, tmp_path):
    window = Session(theme=ThemeManager(QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat))).open_hmi()
    qtbot.addWidget(window)
    dashboard = window.open_dashboard()
    window.show()
    dashboard.show()
    qtbot.waitExposed(dashboard)
    app = QApplication.instance()

    window.theme.set_choice(CHOICE_DARK)

    assert app.palette().color(QPalette.ColorRole.Window) == QColor(DARK.window)
    for plot in (dashboard.power_plot, dashboard.deviation_plot, window.model_view.iv_plot, window.model_view.pv_plot):
        assert plot.backgroundBrush().color() == QColor(DARK.chart_background)
        assert plot.getAxis("left").pen().color() == QColor(DARK.muted_text)
    assert dashboard._power_measured.opts["pen"].color() == QColor(DARK.measured)
    for label in dashboard.power_plot.plotItem.legend.items:
        assert DARK.chart_foreground in label[1].item.toHtml().lower()

    window.theme.set_choice(CHOICE_LIGHT)

    assert app.palette().color(QPalette.ColorRole.Window) == QColor(LIGHT.window)
    assert dashboard.power_plot.backgroundBrush().color() == QColor(LIGHT.chart_background)
    assert dashboard._power_measured.opts["pen"].color() == QColor(LIGHT.measured)


def test_a_chart_created_after_a_theme_change_starts_in_that_theme(qtbot, tmp_path):
    window = Session(theme=ThemeManager(QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat))).open_hmi()
    qtbot.addWidget(window)
    window.theme.set_choice(CHOICE_DARK)

    view = ModelView(window.playback, window.bus, theme=window.theme)
    qtbot.addWidget(view)

    assert view.iv_plot.backgroundBrush().color() == QColor(DARK.chart_background)
    assert view.pv_plot.getAxis("bottom").pen().color() == QColor(DARK.muted_text)
