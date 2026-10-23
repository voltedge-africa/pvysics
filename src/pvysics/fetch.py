"""Fetch a Profile from the NASA POWER hourly point API, with a disk cache. Headless: no Qt.

ProfileFetcher checks the FetchOptions, builds the request URL, and reads the raw response from the
cache when that request was fetched before. Otherwise it asks the transport for the response and
parses it with the same checks as a CSV profile (profile.parse_profile_table). Only a response that
parses is cached, keyed by a hash of the request URL. A cache file that no longer parses is ignored
and fetched again.

The transport is injected. The GUI passes http_transport, which uses urllib with a timeout. The tests
pass a fake, so the suite never touches the network. Every failure is a FetchError, and each kind
says how it is logged: a rejected option or bad data is a WARNING, a network or service failure an ERROR.
"""

import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pvysics.profile import NASA_TIMESTAMP, ColumnMap, Profile, ProfileError, parse_profile_table

API_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"
COMMUNITY = "RE"
TEMPERATURE_PARAMETER = "T2M"
MAX_DAYS = 31  # the most days one request may ask for, both ends included
TIMEOUT_S = 30.0
OK_STATUS = 200
BEGIN_HEADER = "-BEGIN HEADER-"
END_HEADER = "-END HEADER-"
MAX_SERVICE_MESSAGE = 200  # characters of an error body shown to the user

log = logging.getLogger(__name__)


class Irradiance(Enum):
    """The NASA POWER shortwave parameter: all-sky, or clear-sky with no clouds."""

    ALL_SKY = "ALLSKY_SFC_SW_DWN"
    CLEAR_SKY = "CLRSKY_SFC_SW_DWN"


class TimeStandard(Enum):
    """The clock of the response: local standard time, or UTC."""

    LOCAL = "LST"
    UTC = "UTC"


_IRRADIANCE_WORDS = {Irradiance.ALL_SKY: "all-sky", Irradiance.CLEAR_SKY: "clear-sky"}


class FetchError(Exception):
    """A fetch that did not give a profile. Each kind sets the level it is logged at."""

    level = logging.ERROR


class OptionsError(FetchError):
    """The options were rejected before any request was sent."""

    level = logging.WARNING


class NetworkError(FetchError):
    """No network, or the request timed out."""

    level = logging.ERROR


class ServiceError(FetchError):
    """The service answered with an HTTP error status."""

    level = logging.ERROR


class DataError(FetchError):
    """The response could not be parsed, or it has missing or invalid values."""

    level = logging.WARNING


@dataclass(frozen=True)
class FetchOptions:
    """What to fetch: a point, a date range with both ends included, the irradiance and the time standard."""

    latitude: float
    longitude: float
    start: date
    end: date
    irradiance: Irradiance = Irradiance.ALL_SKY
    time_standard: TimeStandard = TimeStandard.LOCAL


@dataclass(frozen=True)
class Response:
    """The HTTP status and the body text of one answer from the service."""

    status: int
    text: str


Transport = Callable[[str], Response]  # request URL -> Response; raises OSError when there is no network


@dataclass(frozen=True)
class FetchResult:
    profile: Profile
    from_cache: bool


def default_dates(today: date) -> tuple[date, date]:
    """A recent past three-day range: it ends a week before today, so the data is certainly published."""
    end = today - timedelta(days=7)
    return end - timedelta(days=2), end


def check_options(options: FetchOptions, today: date) -> None:
    """Raise OptionsError with the first rule the options break. Nothing is requested for a rejected fetch."""
    if not -90.0 <= options.latitude <= 90.0:
        raise OptionsError(f"latitude must be between -90 and 90 degrees, not {options.latitude:g}")
    if not -180.0 <= options.longitude <= 180.0:
        raise OptionsError(f"longitude must be between -180 and 180 degrees, not {options.longitude:g}")
    if options.end < options.start:
        raise OptionsError(f"the end date {options.end} is before the start date {options.start}")
    if options.start > today:
        raise OptionsError(f"the start date {options.start} is in the future")
    if options.end > today:
        raise OptionsError(f"the end date {options.end} is in the future")
    days = (options.end - options.start).days + 1
    if days > MAX_DAYS:
        raise OptionsError(f"the range is {days} days; one fetch can ask for at most {MAX_DAYS}")


def build_url(options: FetchOptions) -> str:
    """The NASA POWER request for the options: the irradiance and T2M, CSV, the dates and the time standard."""
    query = [
        ("parameters", f"{options.irradiance.value},{TEMPERATURE_PARAMETER}"),
        ("community", COMMUNITY),
        ("longitude", _coordinate(options.longitude)),
        ("latitude", _coordinate(options.latitude)),
        ("start", options.start.strftime("%Y%m%d")),
        ("end", options.end.strftime("%Y%m%d")),
        ("format", "CSV"),
        ("time-standard", options.time_standard.value),
    ]
    return f"{API_URL}?{urllib.parse.urlencode(query, safe=',')}"


def profile_name(options: FetchOptions) -> str:
    """The name the fetched Profile carries: the point, the dates, the irradiance and the time standard."""
    return (
        f"NASA POWER {_coordinate(options.latitude)}, {_coordinate(options.longitude)} "
        f"{options.start} to {options.end}, {_IRRADIANCE_WORDS[options.irradiance]}, "
        f"{options.time_standard.value}"
    )


def parse_response(text: str, options: FetchOptions) -> Profile:
    """Build the Profile from a response: skip the text header, then read the hourly rows with the shared checks."""
    columns = ColumnMap(
        timestamp=NASA_TIMESTAMP,
        irradiance=options.irradiance.value,
        temperature=TEMPERATURE_PARAMETER,
    )
    try:
        return parse_profile_table(_data_text(text), columns, name=profile_name(options))
    except ProfileError as error:
        raise DataError(str(error)) from error


def http_transport(url: str) -> Response:
    """The real transport: one GET with a timeout and a User-Agent. HTTP error statuses come back as Responses."""
    request = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as reply:
            return Response(reply.status, reply.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        return Response(error.code, error.read().decode("utf-8", errors="replace"))


class ProfileFetcher:
    """Fetches profiles through one transport and one cache directory. Safe to call from a worker thread."""

    def __init__(self, transport: Transport, cache_dir: Path) -> None:
        self._transport = transport
        self._cache_dir = cache_dir

    def fetch(self, options: FetchOptions, today: date | None = None) -> FetchResult:
        """The profile for the options, from the cache when it holds the request, else from the service.

        Raises FetchError. The error is logged at its kind's level, and nothing is cached unless it parses.
        """
        try:
            return self._fetch(options, today or date.today())
        except FetchError as error:
            log.log(error.level, "Fetch failed: %s", error)
            raise

    def _fetch(self, options: FetchOptions, today: date) -> FetchResult:
        check_options(options, today)
        url = build_url(options)
        path = self._cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.csv"
        cached = self._read_cache(path, options)
        if cached is not None:
            log.info("Fetch served from cache: %s, %d samples", cached.name, len(cached.timestamps))
            return FetchResult(cached, from_cache=True)

        log.info("Fetch started: %s", profile_name(options))
        try:
            response = self._transport(url)
        except OSError as error:
            raise NetworkError(f"could not reach NASA POWER: {error}") from error
        if response.status != OK_STATUS:
            message = _service_message(response.text)
            suffix = f": {message}" if message else ""
            raise ServiceError(f"NASA POWER returned HTTP {response.status}{suffix}")
        profile = parse_response(response.text, options)
        self._write_cache(path, response.text)
        log.info("Fetch finished from the network: %s, %d samples", profile.name, len(profile.timestamps))
        return FetchResult(profile, from_cache=False)

    def _read_cache(self, path: Path, options: FetchOptions) -> Profile | None:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as error:
            log.warning("Cache file %s cannot be read, fetching again: %s", path.name, error)
            return None
        try:
            return parse_response(text, options)
        except DataError as error:
            log.warning("Cache file %s is not valid, fetching again: %s", path.name, error)
            return None

    def _write_cache(self, path: Path, text: str) -> None:
        temporary = path.with_suffix(".tmp")
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)  # whole file or nothing, so a reader never sees half a response
        except OSError as error:
            log.warning("The fetch is not cached: %s", error)


def _coordinate(value: float) -> str:
    return f"{round(value, 4):g}"


def _data_text(text: str) -> str:
    """The response without its text header: the lines between -BEGIN HEADER- and -END HEADER-, if there are any."""
    lines = text.splitlines()
    marks = [line.strip() for line in lines]
    if BEGIN_HEADER not in marks:
        return text
    begin = marks.index(BEGIN_HEADER)
    if END_HEADER not in marks[begin:]:
        raise DataError("the response header has no -END HEADER- line")
    end = begin + marks[begin:].index(END_HEADER)
    return "\n".join(lines[end + 1 :])


def _service_message(body: str) -> str:
    """The message the service gives with an error, when its JSON body has one. A plain or HTML body is not shown."""
    try:
        payload = json.loads(body)
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        for key in ("messages", "message", "detail", "errors"):
            value = payload.get(key)
            if value:
                items = value if isinstance(value, list) else [value]
                return " ".join(str(item) for item in items)[:MAX_SERVICE_MESSAGE]
    return ""


def _user_agent() -> str:
    try:
        release = version("pvysics")
    except PackageNotFoundError:
        release = "dev"
    return f"pvysics/{release} (PV digital twin; profile fetch)"
