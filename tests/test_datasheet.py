from importlib.resources import files
import json

import pytest

from pvysics.datasheet import (
    CUSTOM_MODULE_NAME,
    DatasheetError,
    edited_datasheet,
    load_datasheet,
    load_generic_datasheet,
)


def test_generic_datasheet_matches_the_250_w_module():
    datasheet = load_generic_datasheet()

    assert datasheet.ns == 60
    assert datasheet.pmpp_w == pytest.approx(250.0)
    assert datasheet.isc_a == pytest.approx(8.9)
    assert datasheet.voc_v == pytest.approx(37.8)
    assert datasheet.impp_a == pytest.approx(8.3)
    assert datasheet.vmpp_v == pytest.approx(30.1)
    assert datasheet.ki_pct_per_c == pytest.approx(0.05)
    assert datasheet.kv_pct_per_c == pytest.approx(-0.32)


JSON_DATASHEET = {"Isc": 9.1, "Voc": 36.5, "Impp": 8.0, "Vmpp": 29.5, "Ki": 0.04, "Kv": -0.3, "Ns": 60}


def write_json(tmp_path, content) -> str:
    path = tmp_path / "my_module.json"
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return str(path)


def test_json_datasheet_loads_with_the_keys_of_the_datasheet(tmp_path):
    datasheet = load_datasheet(write_json(tmp_path, JSON_DATASHEET))

    assert datasheet.name == "my_module"
    assert datasheet.ns == 60
    assert datasheet.isc_a == pytest.approx(9.1)
    assert datasheet.voc_v == pytest.approx(36.5)
    assert datasheet.impp_a == pytest.approx(8.0)
    assert datasheet.vmpp_v == pytest.approx(29.5)
    assert datasheet.ki_pct_per_c == pytest.approx(0.04)
    assert datasheet.kv_pct_per_c == pytest.approx(-0.3)
    assert datasheet.pmpp_w == pytest.approx(29.5 * 8.0)


def test_toml_datasheet_loads_in_the_existing_format(tmp_path):
    generic = files("pvysics") / "data" / "generic_60cell_250w.toml"
    path = tmp_path / "generic.toml"
    path.write_text(generic.read_text(encoding="utf-8"), encoding="utf-8")

    assert load_datasheet(path) == load_generic_datasheet()


def test_json_datasheet_saved_with_a_byte_order_mark_loads(tmp_path):
    # Windows editors can save UTF-8 with a byte-order mark; the file is still a valid datasheet.
    path = tmp_path / "bom_module.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(JSON_DATASHEET).encode("utf-8"))

    assert load_datasheet(path).isc_a == pytest.approx(9.1)


def test_toml_datasheet_saved_with_a_byte_order_mark_loads(tmp_path):
    generic = files("pvysics") / "data" / "generic_60cell_250w.toml"
    path = tmp_path / "generic_bom.toml"
    path.write_bytes(b"\xef\xbb\xbf" + generic.read_bytes())

    assert load_datasheet(path) == load_generic_datasheet()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "not valid JSON"),
        ("[1, 2, 3]", "JSON object"),
        ({k: v for k, v in JSON_DATASHEET.items() if k != "Voc"}, "Voc"),
        ({**JSON_DATASHEET, "Isc": "abc"}, "Isc"),
        ({**JSON_DATASHEET, "Isc": -1.0}, "Isc"),
        ({**JSON_DATASHEET, "Ns": 60.5}, "Ns"),
        ({**JSON_DATASHEET, "Vmpp": 40.0}, "Vmpp"),
        ({**JSON_DATASHEET, "Impp": 9.5}, "Impp"),
    ],
)
def test_malformed_or_incomplete_datasheet_is_rejected_with_a_message(tmp_path, content, message):
    with pytest.raises(DatasheetError, match=message):
        load_datasheet(write_json(tmp_path, content))


def test_unsupported_file_type_is_rejected(tmp_path):
    path = tmp_path / "module.txt"
    path.write_text("Isc 9", encoding="utf-8")

    with pytest.raises(DatasheetError, match="json or .toml"):
        load_datasheet(path)


def test_edited_datasheet_is_a_custom_module_with_pmpp_from_vmpp_and_impp():
    generic = load_generic_datasheet()

    edited = edited_datasheet(generic, isc_a=9.3, kv_pct_per_c=-0.3)

    assert edited.name == CUSTOM_MODULE_NAME
    assert edited.isc_a == pytest.approx(9.3)
    assert edited.kv_pct_per_c == pytest.approx(-0.3)
    assert edited.voc_v == generic.voc_v
    assert edited.pmpp_w == pytest.approx(generic.vmpp_v * generic.impp_a)
    assert generic.name == "Generic 60-cell 250 W"  # the base module is not changed
