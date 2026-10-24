import subprocess
import sys

import pytest

from pvysics.gui.cli import ALL, BOTH, DASHBOARD, HMI, SENSORS, parse_opening


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
