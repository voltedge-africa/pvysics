"""The log model: a bounded, filterable buffer of log entries. Headless, no Qt."""

import ast
import logging
import time
from pathlib import Path

import pytest

from pvysics.log_model import LogEntry, LogModel, entry_from_record, format_entry

SRC = Path(__file__).resolve().parents[1] / "src" / "pvysics"


def entry(message: str, level: int = logging.INFO, created: float = 1_700_000_000.0) -> LogEntry:
    return LogEntry(timestamp=created, level=level, logger="pvysics.test", message=message)


def test_entries_keep_the_order_they_were_added_in():
    model = LogModel()
    for index in range(5):
        model.append(entry(f"line {index}"))

    assert [item.message for item in model.visible()] == [f"line {index}" for index in range(5)]


def test_oldest_entries_are_dropped_past_the_bound():
    model = LogModel()  # the default bound
    for index in range(model.capacity + 3):
        model.append(entry(f"line {index}"))

    messages = [item.message for item in model.visible()]
    assert model.capacity == 2000
    assert len(messages) == 2000
    assert messages[0] == "line 3"
    assert messages[-1] == f"line {model.capacity + 2}"


def test_the_bound_is_configurable():
    model = LogModel(capacity=2)
    for message in ("a", "b", "c"):
        model.append(entry(message))

    assert [item.message for item in model.visible()] == ["b", "c"]


def test_a_level_threshold_hides_lower_entries_without_deleting_them():
    model = LogModel()
    model.append(entry("debug", logging.DEBUG))
    model.append(entry("info", logging.INFO))
    model.append(entry("warning", logging.WARNING))

    model.set_threshold(logging.WARNING)
    assert [item.message for item in model.visible()] == ["warning"]
    assert len(model) == 3

    model.set_threshold(logging.DEBUG)
    assert [item.message for item in model.visible()] == ["debug", "info", "warning"]


def test_the_default_threshold_is_info():
    model = LogModel()

    assert model.threshold == logging.INFO


def test_clear_empties_the_buffer_but_keeps_the_threshold():
    model = LogModel()
    model.set_threshold(logging.ERROR)
    model.append(entry("error", logging.ERROR))

    model.clear()

    assert len(model) == 0
    assert model.visible() == ()
    assert model.threshold == logging.ERROR


def test_text_renders_visible_entries_one_per_line_as_time_level_message():
    created = time.mktime((2025, 1, 15, 9, 5, 7, 0, 0, -1))
    model = LogModel()
    model.append(entry("run started", logging.INFO, created))
    model.append(entry("alarm raised", logging.WARNING, created + 1))
    model.append(entry("hidden", logging.DEBUG, created + 2))
    model.set_threshold(logging.INFO)

    lines = model.as_text().split("\n")

    assert lines == [
        "09:05:07 INFO    run started",
        "09:05:08 WARNING alarm raised",
    ]


def test_a_message_with_line_breaks_still_renders_as_one_line():
    created = time.mktime((2025, 1, 15, 9, 5, 7, 0, 0, -1))
    model = LogModel()
    model.append(entry("first part\nsecond part", logging.INFO, created))

    assert model.as_text() == "09:05:07 INFO    first part second part"


def test_text_of_an_empty_model_is_empty():
    assert LogModel().as_text() == ""


def test_format_entry_uses_the_level_name():
    line = format_entry(entry("boom", logging.ERROR))

    assert line.split(" ", 1)[1].split()[0] == "ERROR"
    assert line.endswith("boom")


def test_entry_from_a_record_keeps_level_logger_and_message():
    record = logging.LogRecord(
        name="pvysics.gui.session",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Setup %s rejected",
        args=("CSV",),
        exc_info=None,
    )

    converted = entry_from_record(record)

    assert converted.level == logging.WARNING
    assert converted.logger == "pvysics.gui.session"
    assert converted.message == "Setup CSV rejected"
    assert converted.timestamp == pytest.approx(record.created)


def test_engine_modules_import_no_qt():
    """Everything outside src/pvysics/gui/ is headless: no PyQt6 or pyqtgraph import anywhere in it."""
    offenders = []
    for path in SRC.rglob("*.py"):
        if "gui" in path.relative_to(SRC).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".")[0] in {"PyQt6", "pyqtgraph"}:
                    offenders.append(f"{path.name}: {name}")

    assert offenders == []
