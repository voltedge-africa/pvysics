from datetime import date

import numpy as np
import pytest

from pvysics.profile import (
    BUNDLED_DAYS,
    NASA_TIMESTAMP,
    ColumnMap,
    ProfileError,
    csv_columns,
    guess_columns,
    load_bundled_profile,
    parse_profile_csv,
    parse_profile_table,
)

HEADER = "YEAR,MO,DY,HR,ALLSKY_SFC_SW_DWN,T2M"


def day_csv(irradiance=None, temperature="20.0", drop_hours=(), reverse=False):
    """CSV text for 2025-01-15, one row per hour, with optional overrides."""
    irradiance = irradiance or {}
    rows = [
        f"2025,1,15,{hour},{irradiance.get(hour, '0.0')},{temperature}"
        for hour in range(24)
        if hour not in drop_hours
    ]
    if reverse:
        rows.reverse()
    return "\n".join([HEADER, *rows]) + "\n"


def test_bundled_day_is_24_hourly_steps_starting_at_midnight():
    profile = load_bundled_profile(date(2025, 1, 15))

    assert len(profile.timestamps) == 24
    assert profile.timestamps[0] == np.datetime64("2025-01-15T00:00:00")
    assert np.all(np.diff(profile.timestamps) == np.timedelta64(1, "h"))


@pytest.mark.parametrize("day", [date(2025, 1, 15), date(2025, 1, 16), date(2025, 1, 17)])
def test_irradiance_is_never_negative_on_bundled_days(day):
    profile = load_bundled_profile(day)

    assert np.all(profile.irradiance >= 0.0)


def test_bundled_day_is_dark_at_midnight_and_bright_at_midday():
    profile = load_bundled_profile(date(2025, 1, 15))

    assert profile.irradiance[0] == 0.0
    assert profile.irradiance[10] > 300.0


def test_parsed_values_are_kept_for_the_chosen_day():
    profile = parse_profile_csv(day_csv({12: "800.5"}, temperature="31.25"), date(2025, 1, 15))

    assert profile.irradiance[12] == pytest.approx(800.5)
    assert profile.temperature[12] == pytest.approx(31.25)


def test_day_missing_from_the_data_is_rejected():
    with pytest.raises(ProfileError):
        load_bundled_profile(date(2025, 2, 1))


def test_gap_in_hourly_rows_is_rejected():
    with pytest.raises(ProfileError):
        parse_profile_csv(day_csv(drop_hours=(7,)), date(2025, 1, 15))


def test_missing_value_marker_is_rejected():
    with pytest.raises(ProfileError):
        parse_profile_csv(day_csv({9: "-999"}), date(2025, 1, 15))


def test_negative_irradiance_is_rejected():
    with pytest.raises(ProfileError):
        parse_profile_csv(day_csv({9: "-5.0"}), date(2025, 1, 15))


def test_rows_out_of_time_order_are_rejected():
    with pytest.raises(ProfileError):
        parse_profile_csv(day_csv(reverse=True), date(2025, 1, 15))


TABLE_HEADER = "time,ghi,temp_air"


def table_csv(rows: list[str], header: str = TABLE_HEADER) -> str:
    return "\n".join([header, *rows]) + "\n"


def hourly_rows(irradiance: str = "100.0", temperature: str = "20.0", count: int = 3) -> list[str]:
    return [f"2025-01-15T{hour:02d}:00:00,{irradiance},{temperature}" for hour in range(count)]


MAPPING = ColumnMap(timestamp="time", irradiance="ghi", temperature="temp_air")


def test_bundled_days_are_the_three_days_of_the_sample():
    assert BUNDLED_DAYS == (date(2025, 1, 15), date(2025, 1, 16), date(2025, 1, 17))
    assert [load_bundled_profile(day).name for day in BUNDLED_DAYS] == [
        "Bundled 2025-01-15",
        "Bundled 2025-01-16",
        "Bundled 2025-01-17",
    ]


def test_iso_csv_loads_through_the_column_mapping():
    rows = [
        "2025-06-01T08:00:00,250.5,18.0",
        "2025-06-01T09:00:00,400.0,19.5",
        "2025-06-01T10:00:00,520.0,21.0",
    ]
    profile = parse_profile_table(table_csv(rows), MAPPING, name="site.csv")

    assert profile.name == "site.csv"
    assert profile.timestamps[0] == np.datetime64("2025-06-01T08:00:00")
    assert list(profile.irradiance) == [250.5, 400.0, 520.0]
    assert list(profile.temperature) == [18.0, 19.5, 21.0]


def test_columns_are_found_by_the_mapping_not_by_position():
    text = "ambient,ghi,time\n21.0,300.0,2025-06-01 08:00\n22.0,310.0,2025-06-01 09:00\n"
    mapping = ColumnMap(timestamp="time", irradiance="ghi", temperature="ambient")

    profile = parse_profile_table(text, mapping)

    assert list(profile.irradiance) == [300.0, 310.0]
    assert list(profile.temperature) == [21.0, 22.0]


def test_nasa_layout_can_be_mapped_as_the_timestamp():
    text = (
        "YEAR,MO,DY,HR,ALLSKY_SFC_SW_DWN,T2M\n"
        "2025,1,15,0,0.0,26.1\n"
        "2025,1,15,1,0.0,25.9\n"
        "2025,1,15,2,0.0,25.0\n"
    )
    mapping = ColumnMap(
        timestamp=NASA_TIMESTAMP, irradiance="ALLSKY_SFC_SW_DWN", temperature="T2M"
    )

    profile = parse_profile_table(text, mapping)

    assert profile.timestamps[2] == np.datetime64("2025-01-15T02:00:00")


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("timestamp,G,T", ColumnMap("timestamp", "G", "T")),
        ("YEAR,MO,DY,HR,ALLSKY_SFC_SW_DWN,T2M", ColumnMap(NASA_TIMESTAMP, "ALLSKY_SFC_SW_DWN", "T2M")),
        ("time,ghi,temp_air", ColumnMap("time", "ghi", "temp_air")),
        ("Date,Irradiance,Pressure", ColumnMap("Date", "Irradiance", "")),
    ],
)
def test_guess_columns_finds_the_common_names(header, expected):
    assert guess_columns(header.split(",")) == expected


def test_header_lists_the_columns_of_the_file():
    assert csv_columns(table_csv([])) == ["time", "ghi", "temp_air"]


def test_file_without_a_header_is_rejected():
    with pytest.raises(ProfileError):
        csv_columns("")


def test_missing_column_is_named_in_the_error():
    text = table_csv(hourly_rows(), header="time,ghi")

    with pytest.raises(ProfileError, match="'temp_air'"):
        parse_profile_table(text, MAPPING)


def test_unchosen_column_is_rejected_with_its_role():
    mapping = ColumnMap(timestamp="time", irradiance="ghi", temperature="")

    with pytest.raises(ProfileError, match="temperature"):
        parse_profile_table(table_csv(hourly_rows()), mapping)


def test_same_column_for_irradiance_and_temperature_is_rejected():
    mapping = ColumnMap(timestamp="time", irradiance="ghi", temperature="ghi")

    with pytest.raises(ProfileError):
        parse_profile_table(table_csv(hourly_rows()), mapping)


def test_non_numeric_value_is_rejected_with_its_row():
    rows = hourly_rows()
    rows[1] = "2025-01-15T01:00:00,n/a,20.0"

    with pytest.raises(ProfileError, match="row 2.*not a number"):
        parse_profile_table(table_csv(rows), MAPPING)


def test_short_row_is_rejected_as_missing_a_value():
    rows = hourly_rows()
    rows[2] = "2025-01-15T02:00:00,100.0"

    with pytest.raises(ProfileError, match="missing"):
        parse_profile_table(table_csv(rows), MAPPING)


@pytest.mark.parametrize("marker", ["-999", "nan", "inf"])
def test_missing_marker_and_non_finite_values_are_rejected(marker):
    rows = hourly_rows()
    rows[0] = f"2025-01-15T00:00:00,{marker},20.0"

    with pytest.raises(ProfileError):
        parse_profile_table(table_csv(rows), MAPPING)


def test_unparseable_timestamp_is_rejected():
    rows = hourly_rows()
    rows[0] = "15/01/2025 00:00,100.0,20.0"

    with pytest.raises(ProfileError, match="timestamp"):
        parse_profile_table(table_csv(rows), MAPPING)


def test_decreasing_time_in_the_table_is_rejected():
    with pytest.raises(ProfileError, match="does not increase"):
        parse_profile_table(table_csv(list(reversed(hourly_rows()))), MAPPING)


def test_repeated_timestamp_is_rejected_as_not_increasing():
    rows = [hourly_rows()[0], hourly_rows()[0]]

    with pytest.raises(ProfileError, match="does not increase"):
        parse_profile_table(table_csv(rows), MAPPING)


def test_gap_in_the_table_is_rejected():
    rows = ["2025-01-15T00:00:00,0.0,20.0", "2025-01-15T01:00:00,0.0,20.0", "2025-01-15T03:00:00,0.0,20.0"]

    with pytest.raises(ProfileError, match="gap"):
        parse_profile_table(table_csv(rows), MAPPING)


def test_negative_irradiance_in_the_table_is_rejected():
    rows = hourly_rows()
    rows[1] = "2025-01-15T01:00:00,-5.0,20.0"

    with pytest.raises(ProfileError, match="negative"):
        parse_profile_table(table_csv(rows), MAPPING)


def test_table_needs_at_least_two_rows():
    with pytest.raises(ProfileError):
        parse_profile_table(table_csv(hourly_rows(count=1)), MAPPING)
    with pytest.raises(ProfileError):
        parse_profile_table(table_csv([]), MAPPING)


# ---- Excel profiles and the weather template ---------------------------------------------------------------------

import zipfile  # noqa: E402

from pvysics.profile import (  # noqa: E402
    PROFILE_TEMPLATE_HEADER,
    PROFILE_TEMPLATE_ROWS,
    read_profile_text,
    write_profile_template,
)


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_the_weather_template_loads_as_a_valid_profile(tmp_path, suffix):
    path = tmp_path / f"weather{suffix}"

    write_profile_template(path)
    text = read_profile_text(path)
    profile = parse_profile_table(text, guess_columns(csv_columns(text)), "template")

    assert len(profile.timestamps) == len(PROFILE_TEMPLATE_ROWS) == 24
    assert profile.irradiance.max() == pytest.approx(900.0)
    assert profile.irradiance.min() == 0.0
    assert csv_columns(text) == list(PROFILE_TEMPLATE_HEADER)


def test_an_excel_profile_with_date_serials_is_read_as_times(tmp_path):
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rows = [("Timestamp", "G", "T"), (45672.375, 250.5, 18.0), (45672.4166667, 400.0, 19.5), (45672.4583333, 520.0, 21.0)]
    strings = list(rows[0])
    cells = []
    for number, row in enumerate(rows, start=1):
        items = []
        for column, value in enumerate(row):
            ref = f"{'ABC'[column]}{number}"
            items.append(f'<c r="{ref}" t="s"><v>{strings.index(value)}</v></c>' if isinstance(value, str) else f'<c r="{ref}"><v>{value}</v></c>')
        cells.append(f'<row r="{number}">{"".join(items)}</row>')
    path = tmp_path / "site.xlsx"
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("xl/sharedStrings.xml", f'<sst xmlns="{main}">' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        book.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{main}"><sheetData>{"".join(cells)}</sheetData></worksheet>')

    text = read_profile_text(path)
    profile = parse_profile_table(text, guess_columns(csv_columns(text)), "site")

    assert str(profile.timestamps[0]) == "2025-01-15T09:00:00"
    assert str(profile.timestamps[2]) == "2025-01-15T11:00:00"
    assert profile.irradiance.tolist() == [250.5, 400.0, 520.0]


def test_a_profile_file_of_another_type_is_refused(tmp_path):
    path = tmp_path / "weather.txt"
    path.write_text("x", encoding="utf-8")

    with pytest.raises(ProfileError, match="not a .csv or .xlsx"):
        read_profile_text(path)


def test_a_broken_workbook_is_reported_not_raised_raw(tmp_path):
    path = tmp_path / "fake.xlsx"
    path.write_text("not a zip", encoding="utf-8")

    with pytest.raises(ProfileError, match="cannot read fake.xlsx"):
        read_profile_text(path)


def test_the_weather_template_only_comes_as_csv_or_xlsx(tmp_path):
    with pytest.raises(ProfileError):
        write_profile_template(tmp_path / "t.pdf")
