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


# ---- CSV and Excel datasheets, and the template ------------------------------------------------------------------

import zipfile  # noqa: E402

from pvysics.datasheet import TEMPLATE_ROWS, write_datasheet_template  # noqa: E402


def excel_table(path, rows):
    """A workbook as Excel writes it, with text through a shared-strings table."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    strings = []
    cells = []
    for number, row in enumerate(rows, start=1):
        items = []
        for column, value in enumerate(row):
            ref = f"{'ABCD'[column]}{number}"
            if isinstance(value, str):
                strings.append(value)
                items.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
            else:
                items.append(f'<c r="{ref}"><v>{value}</v></c>')
        cells.append(f'<row r="{number}">{"".join(items)}</row>')
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("xl/sharedStrings.xml", f'<sst xmlns="{main}">' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        book.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{main}"><sheetData>{"".join(cells)}</sheetData></worksheet>')


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_the_datasheet_template_loads_as_a_valid_module(tmp_path, suffix):
    path = tmp_path / f"module{suffix}"

    write_datasheet_template(path)
    datasheet = load_datasheet(path)

    assert datasheet.name == "My module"
    assert datasheet.ns == 60
    assert datasheet.isc_a == TEMPLATE_ROWS[1][1]
    assert datasheet.kv_pct_per_c == pytest.approx(-0.32)
    assert datasheet.pmpp_w == pytest.approx(datasheet.vmpp_v * datasheet.impp_a)


def test_the_excel_datasheet_template_has_an_instructions_sheet(tmp_path):
    write_datasheet_template(tmp_path / "t.xlsx")

    with zipfile.ZipFile(tmp_path / "t.xlsx") as book:
        assert b"Datasheet" in book.read("xl/workbook.xml")
        assert b"Instructions" in book.read("xl/workbook.xml")


def test_a_csv_datasheet_may_use_any_case_units_in_names_and_an_optional_rated_power(tmp_path):
    path = tmp_path / "Trina.csv"
    path.write_text(
        "Parameter,Value\nISC (A),9.1\nVoc,36.5\nImpp,8.0\nVmpp,29.5\nKi,0.04\nKv,-0.3\nCells,60\nPmpp,236\nnote,anything\n",
        encoding="utf-8",
    )

    datasheet = load_datasheet(path)

    assert datasheet.name == "Trina"  # no name row: the file's
    assert datasheet.pmpp_w == 236.0
    assert datasheet.isc_a == 9.1


def test_an_excel_datasheet_with_shared_strings_loads(tmp_path):
    path = tmp_path / "book.xlsx"
    excel_table(
        path,
        [("parameter", "value"), ("Isc", 9.1), ("Voc", 36.5), ("Impp", 8.0), ("Vmpp", 29.5), ("Ki", 0.04), ("Kv", -0.3), ("Ns", 60)],
    )

    assert load_datasheet(path).ns == 60


def test_a_table_datasheet_missing_a_row_names_it(tmp_path):
    path = tmp_path / "short.csv"
    path.write_text("parameter,value\nIsc,9.1\nVoc,36.5\n", encoding="utf-8")

    with pytest.raises(DatasheetError, match="missing .*Impp"):
        load_datasheet(path)


def test_a_table_datasheet_with_text_in_a_value_cell_is_refused(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("parameter,value\nIsc,eight\n", encoding="utf-8")

    with pytest.raises(DatasheetError, match="Isc must be a number"):
        load_datasheet(path)


def test_a_fractional_cell_count_is_refused(tmp_path):
    path = tmp_path / "cells.csv"
    path.write_text("parameter,value\nIsc,9.1\nVoc,36.5\nImpp,8\nVmpp,29.5\nKi,0.04\nKv,-0.3\nNs,60.5\n", encoding="utf-8")

    with pytest.raises(DatasheetError, match="whole number"):
        load_datasheet(path)


def test_the_datasheet_template_only_comes_as_csv_or_xlsx(tmp_path):
    with pytest.raises(DatasheetError):
        write_datasheet_template(tmp_path / "t.pdf")
