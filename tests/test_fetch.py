"""The NASA POWER fetch client, driven by fake transports. No test here touches the network."""

import io
import logging
import urllib.error
from datetime import date
from importlib.resources import files
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest

from pvysics import fetch
from pvysics.fetch import (
    DataError,
    FetchOptions,
    Irradiance,
    NetworkError,
    OptionsError,
    ProfileFetcher,
    Response,
    ServiceError,
    TimeStandard,
    build_url,
    check_options,
    default_dates,
    http_transport,
)

TODAY = date(2026, 10, 23)
DURBAN = FetchOptions(
    latitude=-29.85,
    longitude=31.00,
    start=date(2025, 1, 15),
    end=date(2025, 1, 17),
)
HEADER = """-BEGIN HEADER-
NASA/POWER CERES/MERRA2 Native Resolution Hourly Data
Dates (month/day/year): 01/15/2025 through 01/17/2025
Location: Latitude -29.85 Longitude 31
Elevation from MERRA-2: Average for 0.5 x 0.625 Deg. Lat/Lon region = 15.2 m
Value for missing model data cannot be computed or out of model availability range: -999
-END HEADER-
"""


def bundled_rows() -> list[str]:
    """The 72 hourly rows of the bundled sample, 15 to 17 January 2025, as the service sends them."""
    text = (files("pvysics") / "data" / "durban_power_hourly.csv").read_text(encoding="utf-8")
    return text.splitlines()[1:]


def response_text(irradiance: str = "ALLSKY_SFC_SW_DWN", rows: list[str] | None = None) -> str:
    body = rows if rows is not None else bundled_rows()
    return HEADER + "YEAR,MO,DY,HR," + irradiance + ",T2M\n" + "\n".join(body) + "\n"


class FakeTransport:
    """Records each request URL and returns a canned response, or raises the given error."""

    def __init__(self, text: str = "", status: int = 200, error: BaseException | None = None) -> None:
        self.text = text
        self.status = status
        self.error = error
        self.urls: list[str] = []

    def __call__(self, url: str) -> Response:
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        return Response(self.status, self.text)


def query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


def test_all_sky_request_asks_for_the_all_sky_parameter_and_t2m():
    url = build_url(DURBAN)

    assert query(url)["parameters"] == ["ALLSKY_SFC_SW_DWN,T2M"]


def test_clear_sky_request_asks_for_the_clear_sky_parameter_and_t2m():
    url = build_url(FetchOptions(**{**DURBAN.__dict__, "irradiance": Irradiance.CLEAR_SKY}))

    assert query(url)["parameters"] == ["CLRSKY_SFC_SW_DWN,T2M"]


def test_request_carries_the_point_dates_format_and_time_standard():
    params = query(build_url(DURBAN))

    assert urlparse(build_url(DURBAN)).netloc == "power.larc.nasa.gov"
    assert params["community"] == ["RE"]
    assert params["latitude"] == ["-29.85"]
    assert params["longitude"] == ["31"]
    assert params["start"] == ["20250115"]
    assert params["end"] == ["20250117"]
    assert params["format"] == ["CSV"]
    assert params["time-standard"] == ["LST"]


def test_utc_time_standard_is_sent_as_utc():
    url = build_url(FetchOptions(**{**DURBAN.__dict__, "time_standard": TimeStandard.UTC}))

    assert query(url)["time-standard"] == ["UTC"]


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (FetchOptions(-90.5, 31.0, date(2025, 1, 15), date(2025, 1, 17)), "latitude must be between -90 and 90"),
        (FetchOptions(91.0, 31.0, date(2025, 1, 15), date(2025, 1, 17)), "latitude must be between -90 and 90"),
        (FetchOptions(-29.0, 180.5, date(2025, 1, 15), date(2025, 1, 17)), "longitude must be between -180 and 180"),
        (FetchOptions(-29.0, 31.0, date(2025, 1, 17), date(2025, 1, 15)), "is before the start date"),
        (FetchOptions(-29.0, 31.0, date(2026, 10, 24), date(2026, 10, 25)), "start date 2026-10-24 is in the future"),
        (FetchOptions(-29.0, 31.0, date(2026, 10, 20), date(2026, 10, 30)), "end date 2026-10-30 is in the future"),
        (FetchOptions(-29.0, 31.0, date(2025, 1, 1), date(2025, 2, 1)), "the range is 32 days"),
    ],
)
def test_rejected_options_give_a_specific_message(options, message):
    with pytest.raises(OptionsError, match=message):
        check_options(options, TODAY)


def test_a_thirty_one_day_range_is_accepted():
    check_options(FetchOptions(-29.0, 31.0, date(2025, 1, 1), date(2025, 1, 31)), TODAY)


def test_default_dates_are_a_three_day_range_ending_a_week_ago():
    assert default_dates(TODAY) == (date(2026, 10, 14), date(2026, 10, 16))


def test_a_fetch_parses_the_response_into_a_profile(tmp_path):
    transport = FakeTransport(response_text())
    result = ProfileFetcher(transport, tmp_path).fetch(DURBAN, today=TODAY)

    assert result.from_cache is False
    assert len(result.profile.timestamps) == 72
    assert result.profile.timestamps[0] == np.datetime64("2025-01-15T00:00:00")
    assert result.profile.timestamps[-1] == np.datetime64("2025-01-17T23:00:00")
    assert result.profile.irradiance.max() > 0.0
    assert result.profile.name == "NASA POWER -29.85, 31 2025-01-15 to 2025-01-17, all-sky, LST"


def test_clear_sky_response_is_read_from_the_clear_sky_column(tmp_path):
    rows = ["2025,1,15,12,700.0,30.0", "2025,1,15,13,650.0,30.5"]
    text = response_text("CLRSKY_SFC_SW_DWN", rows)
    options = FetchOptions(**{**DURBAN.__dict__, "irradiance": Irradiance.CLEAR_SKY, "start": date(2025, 1, 15), "end": date(2025, 1, 15)})

    profile = ProfileFetcher(FakeTransport(text), tmp_path).fetch(options, today=TODAY).profile

    assert profile.irradiance.tolist() == [700.0, 650.0]


def test_missing_value_marker_is_rejected_with_its_row(tmp_path):
    rows = bundled_rows()
    rows[5] = "2025,1,15,5,-999,25.0"
    transport = FakeTransport(response_text(rows=rows))

    with pytest.raises(DataError, match="-999"):
        ProfileFetcher(transport, tmp_path).fetch(DURBAN, today=TODAY)


def test_bad_body_is_a_data_error_and_is_not_cached(tmp_path):
    transport = FakeTransport("<html><body>Maintenance</body></html>")

    with pytest.raises(DataError):
        ProfileFetcher(transport, tmp_path).fetch(DURBAN, today=TODAY)

    assert list(tmp_path.iterdir()) == []


def test_header_without_an_end_marker_is_a_data_error(tmp_path):
    transport = FakeTransport("-BEGIN HEADER-\nno end line\nYEAR,MO,DY,HR\n")

    with pytest.raises(DataError, match="END HEADER"):
        ProfileFetcher(transport, tmp_path).fetch(DURBAN, today=TODAY)


def test_a_repeat_fetch_is_served_from_cache_without_calling_the_transport(tmp_path):
    transport = FakeTransport(response_text())
    fetcher = ProfileFetcher(transport, tmp_path)
    first = fetcher.fetch(DURBAN, today=TODAY)

    second = fetcher.fetch(DURBAN, today=TODAY)

    assert len(transport.urls) == 1
    assert first.from_cache is False
    assert second.from_cache is True
    assert second.profile.timestamps.tolist() == first.profile.timestamps.tolist()


def test_cache_is_keyed_by_the_request_so_another_irradiance_is_fetched(tmp_path):
    transport = FakeTransport(response_text())
    fetcher = ProfileFetcher(transport, tmp_path)
    fetcher.fetch(DURBAN, today=TODAY)
    clear = FetchOptions(**{**DURBAN.__dict__, "irradiance": Irradiance.CLEAR_SKY})

    transport.text = response_text("CLRSKY_SFC_SW_DWN")
    result = fetcher.fetch(clear, today=TODAY)

    assert len(transport.urls) == 2
    assert result.from_cache is False


def test_corrupt_cache_file_is_ignored_and_fetched_again(tmp_path, caplog):
    transport = FakeTransport(response_text())
    fetcher = ProfileFetcher(transport, tmp_path)
    fetcher.fetch(DURBAN, today=TODAY)
    (cache_file,) = tmp_path.glob("*.csv")
    cache_file.write_text("this is not a profile", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="pvysics.fetch"):
        result = fetcher.fetch(DURBAN, today=TODAY)

    assert len(transport.urls) == 2
    assert result.from_cache is False
    assert "not valid" in caplog.text
    assert len(result.profile.timestamps) == 72


def test_undecodable_cache_file_is_ignored_and_fetched_again(tmp_path):
    transport = FakeTransport(response_text())
    fetcher = ProfileFetcher(transport, tmp_path)
    fetcher.fetch(DURBAN, today=TODAY)
    (cache_file,) = tmp_path.glob("*.csv")
    cache_file.write_bytes(b"\xff\xfe\x00garbage")

    result = fetcher.fetch(DURBAN, today=TODAY)

    assert len(transport.urls) == 2
    assert result.from_cache is False


def test_no_network_is_a_network_error_and_logged_as_an_error(tmp_path, caplog):
    transport = FakeTransport(error=urllib.error.URLError("no route to host"))

    with caplog.at_level(logging.ERROR, logger="pvysics.fetch"):
        with pytest.raises(NetworkError, match="could not reach NASA POWER"):
            ProfileFetcher(transport, tmp_path).fetch(DURBAN, today=TODAY)

    assert "Fetch failed" in caplog.text
    assert list(tmp_path.iterdir()) == []


def test_timeout_is_a_network_error(tmp_path):
    transport = FakeTransport(error=TimeoutError("timed out"))

    with pytest.raises(NetworkError, match="timed out"):
        ProfileFetcher(transport, tmp_path).fetch(DURBAN, today=TODAY)


def test_http_error_gives_the_code_and_the_service_message(tmp_path, caplog):
    body = '{"messages": ["Parameter CLRSKY_SFC_SW_DWN is not available for this point."]}'
    transport = FakeTransport(body, status=422)

    with caplog.at_level(logging.ERROR, logger="pvysics.fetch"):
        with pytest.raises(ServiceError, match="HTTP 422: Parameter CLRSKY_SFC_SW_DWN"):
            ProfileFetcher(transport, tmp_path).fetch(DURBAN, today=TODAY)

    assert "ERROR" in [record.levelname for record in caplog.records]


def test_http_error_without_a_message_gives_only_the_code(tmp_path):
    with pytest.raises(ServiceError, match=r"^NASA POWER returned HTTP 500$"):
        ProfileFetcher(FakeTransport("<h1>Server error</h1>", status=500), tmp_path).fetch(DURBAN, today=TODAY)


def test_rejected_options_make_no_request_and_are_logged_as_a_warning(tmp_path, caplog):
    transport = FakeTransport(response_text())
    bad = FetchOptions(-29.0, 31.0, date(2025, 1, 17), date(2025, 1, 15))

    with caplog.at_level(logging.WARNING, logger="pvysics.fetch"):
        with pytest.raises(OptionsError):
            ProfileFetcher(transport, tmp_path).fetch(bad, today=TODAY)

    assert transport.urls == []
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_a_three_day_fetch_is_a_multi_day_profile(tmp_path):
    profile = ProfileFetcher(FakeTransport(response_text()), tmp_path).fetch(DURBAN, today=TODAY).profile

    days = {str(stamp)[:10] for stamp in profile.timestamps}

    assert days == {"2025-01-15", "2025-01-16", "2025-01-17"}


def test_http_transport_sends_a_timeout_and_a_pvysics_user_agent(monkeypatch):
    seen = {}

    class Reply:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return b"ok"

    def fake_urlopen(request, timeout):
        seen["timeout"] = timeout
        seen["agent"] = request.get_header("User-agent")
        return Reply()

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)

    response = http_transport("https://example.invalid/?x=1")

    assert response == Response(200, "ok")
    assert seen["timeout"] == 30.0
    assert seen["agent"].startswith("pvysics/")


def test_http_transport_returns_an_error_status_instead_of_raising(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 503, "Unavailable", {}, io.BytesIO(b"down"))

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)

    response = http_transport("https://example.invalid/")

    assert response.status == 503
