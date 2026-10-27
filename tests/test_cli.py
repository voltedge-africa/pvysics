import subprocess
import sys

import pytest

from pvysics.gui.cli import ADVANCED_ENV, ALL, BOTH, DASHBOARD, HMI, SENSORS, SIMPLE, advanced_enabled, parse_opening


@pytest.mark.parametrize(
    ("argv", "opening"),
    [
        ([], ALL),
        (["--all"], ALL),
        (["--sensors"], SENSORS),
        (["--hmi"], HMI),
        (["--dashboard"], DASHBOARD),
        (["--both"], BOTH),
    ],
)
def test_each_switch_chooses_the_windows_to_open(argv, opening):
    assert parse_opening(argv) == opening


@pytest.mark.parametrize("argv", [["--hmi", "--dashboard"], ["--both", "--hmi"], ["--dashboard", "--both"], ["--sensors", "--all"]])
def test_conflicting_switches_are_a_usage_error(argv, capsys):
    with pytest.raises(SystemExit) as exit_info:
        parse_opening(argv)

    assert exit_info.value.code != 0
    assert "not allowed with" in capsys.readouterr().err


def test_unknown_switch_prints_usage_and_exits_non_zero_without_a_traceback(capsys):
    with pytest.raises(SystemExit) as exit_info:
        parse_opening(["--bogus"])

    err = capsys.readouterr().err
    assert exit_info.value.code != 0
    assert "usage: pvysics" in err
    assert "--bogus" in err
    assert "Traceback" not in err


def test_cli_imports_without_qt():
    code = (
        "import sys, pvysics.gui.cli; "
        "assert not any(m.startswith('PyQt') for m in sys.modules)"
    )

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_the_app_icon_and_splash_are_valid_svgs_that_render(qtbot):
    from PyQt6.QtSvg import QSvgRenderer

    from pvysics.gui.app import SPLASH_SIZE, _asset, splash_pixmap

    for name in ("icon.svg", "splash.svg"):
        assert QSvgRenderer(_asset(name)).isValid()
    assert splash_pixmap().size().width() >= SPLASH_SIZE.width()


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes", " on "])
def test_advanced_is_on_for_a_true_value(value):
    assert advanced_enabled({ADVANCED_ENV: value})


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "advanced"])
def test_advanced_is_off_for_anything_else(value):
    assert not advanced_enabled({ADVANCED_ENV: value})


def test_advanced_is_off_when_the_variable_is_unset():
    assert not advanced_enabled({})


def test_the_environment_decides_when_advanced_is_not_given(monkeypatch):
    monkeypatch.delenv(ADVANCED_ENV)
    assert parse_opening([]) == SIMPLE
    monkeypatch.setenv(ADVANCED_ENV, "1")
    assert parse_opening([]) == ALL


def test_the_simple_app_opens_one_window_and_takes_no_window_switches(capsys):
    assert parse_opening([], advanced=False) == SIMPLE
    with pytest.raises(SystemExit) as exit_info:
        parse_opening(["--hmi"], advanced=False)

    assert exit_info.value.code != 0
    err = capsys.readouterr().err
    assert "unrecognized arguments: --hmi" in err
    assert ADVANCED_ENV in err or "usage: pvysics" in err
