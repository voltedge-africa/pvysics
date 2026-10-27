"""Spreadsheets: read the first sheet of an Excel workbook, and write a small workbook. Headless, no Qt.

Used for the files a user fills in and uploads (datasets, weather profiles, module datasheets), so Excel
works wherever CSV does, with no extra dependency: an .xlsx file is a zip of XML parts. Reading goes through
CSV text, so every file gets the same checks, whichever format it came in.
"""

import csv
import io
import posixpath
import re
import zipfile
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

EXCEL_EPOCH = datetime(1899, 12, 30)  # the day Excel counts from
EXCEL_SERIAL_RANGE = (20000.0, 80000.0)  # the years 1954 to 2119: a timestamp cell this large is a date Excel saved
MAX_XLSX_BYTES = 100 * 1024 * 1024  # the unpacked size of the workbook's parts, a guard against a zip bomb
XLSX_SUFFIX = ".xlsx"
CSV_SUFFIX = ".csv"


class SpreadsheetError(ValueError):
    """The workbook cannot be read: it is not a workbook, is too large, or is empty."""


def xlsx_to_csv_text(path: Path, timestamp_names: Sequence[str] = ()) -> str:
    """The first sheet of an Excel workbook as CSV text, so it goes through the same checks as a CSV file.

    Numbers keep their value, text stays text, and in the column whose header is one of timestamp_names
    (any case) a cell that Excel saved as a date, which is a serial number, is written as an ISO date and time.
    """
    with zipfile.ZipFile(path) as book:
        if sum(info.file_size for info in book.infolist()) > MAX_XLSX_BYTES:
            raise SpreadsheetError("the workbook is too large to read")
        sheet = _first_sheet_xml(book)
        shared = _shared_strings(book)
        rows = _sheet_rows(sheet, shared)
    if not rows or not any(rows[0]):
        raise SpreadsheetError("the first sheet of the workbook is empty")
    header = [cell.strip() for cell in rows[0]]
    wanted = {name.lower() for name in timestamp_names}
    stamp_index = next((index for index, name in enumerate(header) if name.lower() in wanted), -1)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue  # a blank row Excel kept
        row = row + [""] * (len(header) - len(row))
        if stamp_index >= 0:
            row[stamp_index] = excel_stamp(row[stamp_index])
        writer.writerow(row[: len(header)])
    return out.getvalue()


def write_table(
    path: Path, header: Sequence, rows: Sequence[Sequence], notes: Sequence[Sequence] = (), sheet: str = "Data"
) -> None:
    """Write a table as .csv or .xlsx, by the path's suffix. An Excel file holds it on a sheet named `sheet`, and
    an Instructions sheet from notes."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == CSV_SUFFIX:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
    elif suffix == XLSX_SUFFIX:
        sheets = [(sheet, [tuple(header), *rows])]
        if notes:
            sheets.append(("Instructions", list(notes)))
        write_xlsx(path, sheets)
    else:
        raise SpreadsheetError(f"a template is a .csv or .xlsx file, not '{path.suffix}'")



def excel_stamp(text: str) -> str:
    """A date Excel stored as a serial number, as an ISO date and time; any other text unchanged."""
    try:
        serial = float(text)
    except ValueError:
        return text
    low, high = EXCEL_SERIAL_RANGE
    if not low <= serial <= high:
        return text
    moment = EXCEL_EPOCH + timedelta(seconds=round(serial * 86400.0))
    return moment.isoformat(timespec="seconds")


def _first_sheet_xml(book: zipfile.ZipFile) -> ElementTree.Element:
    """The XML of the workbook's first sheet, found through the workbook's own list, else the usual name."""
    target = "xl/worksheets/sheet1.xml"
    try:
        workbook = ElementTree.fromstring(book.read("xl/workbook.xml"))
        relations = ElementTree.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        sheet = next(element for element in workbook.iter() if _tag(element) == "sheet")
        wanted = next(value for key, value in sheet.attrib.items() if key.endswith("}id"))
        for relation in relations:
            if relation.get("Id") == wanted:
                href = relation.get("Target", "")  # relative to xl/, or absolute from the package root
                target = href.lstrip("/") if href.startswith("/") else posixpath.normpath(posixpath.join("xl", href))
    except (KeyError, StopIteration, ElementTree.ParseError):
        pass  # fall back to the usual name below
    try:
        return ElementTree.fromstring(book.read(target))
    except (KeyError, ElementTree.ParseError) as error:
        raise SpreadsheetError("this is not an Excel workbook that can be read") from error


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    except ElementTree.ParseError as error:
        raise SpreadsheetError("the workbook's text could not be read") from error
    return ["".join(node.text or "" for node in item.iter() if _tag(node) == "t") for item in root if _tag(item) == "si"]


def _sheet_rows(sheet: ElementTree.Element, shared: list[str]) -> list[list[str]]:
    """The cells of a sheet as text, row by row, with gaps filled so each cell sits in its own column."""
    rows: list[list[str]] = []
    for row in (element for element in sheet.iter() if _tag(element) == "row"):
        cells: dict[int, str] = {}
        for position, cell in enumerate(element for element in row if _tag(element) == "c"):
            reference = cell.get("r", "")
            index = _column_index(reference) if reference else position
            cells[index] = _cell_text(cell, shared)
        width = max(cells, default=-1) + 1
        rows.append([cells.get(index, "") for index in range(width)])
    return rows


def _cell_text(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.get("t", "n")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter() if _tag(node) == "t")
    value = next((child.text or "" for child in cell if _tag(child) == "v"), "")
    if kind == "s":
        try:
            return shared[int(value)]
        except (ValueError, IndexError) as error:
            raise SpreadsheetError("the workbook refers to text that is not there") from error
    if kind == "b":
        return "1" if value == "1" else "0"
    return value


def _column_index(reference: str) -> int:
    """The zero-based column of a cell reference such as 'C7'."""
    letters = re.match(r"[A-Za-z]+", reference)
    if not letters:
        raise SpreadsheetError(f"cell '{reference}' has no column")
    index = 0
    for letter in letters.group().upper():
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def _tag(element: ElementTree.Element) -> str:
    """An element's name without its namespace."""
    return element.tag.rsplit("}", 1)[-1]


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def write_xlsx(path: Path, sheets: list[tuple[str, tuple]]) -> None:
    """A minimal workbook: one sheet per (name, rows) with text and numbers, a wide first column and a bold-free header."""
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{number}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for number in range(1, len(sheets) + 1)
            )
            + "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            + "".join(
                f'<sheet name="{escape(name)}" sheetId="{number}" r:id="rId{number}"/>'
                for number, (name, _rows) in enumerate(sheets, start=1)
            )
            + "</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{number}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{number}.xml"/>'
                for number in range(1, len(sheets) + 1)
            )
            + "</Relationships>"
        ),
    }
    for number, (_name, rows) in enumerate(sheets, start=1):
        parts[f"xl/worksheets/sheet{number}.xml"] = _sheet_xml(rows)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as book:
        for name, content in parts.items():
            book.writestr(name, content)


def _sheet_xml(rows) -> str:
    body = []
    widest = 0
    for number, row in enumerate(rows, start=1):
        cells = []
        for index, value in enumerate(row):
            reference = f"{_column_letter(index)}{number}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        widest = max(widest, len(row))
        body.append(f'<row r="{number}">{"".join(cells)}</row>')
    widths = "".join(
        f'<col min="{index}" max="{index}" width="{26 if index == 1 else 18}" customWidth="1"/>'
        for index in range(1, widest + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<cols>{widths}</cols><sheetData>{''.join(body)}</sheetData></worksheet>"
    )
