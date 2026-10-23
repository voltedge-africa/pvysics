"""The Fetch profile group on the Setup tab: fetch options, a fetch on a worker thread, and the staged profile.

A fetch runs on a QThread so the window stays usable. While it runs the controls are disabled, a busy bar
shows, and Cancel is enabled. Cancel cannot stop a request that is already on the wire, so the request
finishes in the background and its result is discarded. The result comes back to the UI thread as a
signal. A fetched profile is only staged here. It becomes the active profile when the user presses
Use fetched profile, and the Setup view takes it from the profile_chosen signal.
"""

import logging
import tempfile
import threading
from datetime import date
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QDate, QObject, QStandardPaths, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pvysics.fetch import (
    FetchError,
    FetchOptions,
    FetchResult,
    Irradiance,
    ProfileFetcher,
    TimeStandard,
    default_dates,
    http_transport,
)
from pvysics.profile import Profile

log = logging.getLogger(__name__)
IRRADIANCE_CHOICES = (("All-sky", Irradiance.ALL_SKY), ("Clear-sky", Irradiance.CLEAR_SKY))
STANDARD_CHOICES = (("Local standard time (LST)", TimeStandard.LOCAL), ("UTC", TimeStandard.UTC))
DATE_FORMAT = "yyyy-MM-dd"


def default_cache_dir() -> Path:
    """The fetch cache: a profiles folder in the platform's user cache location for this app (QStandardPaths)."""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    return Path(location or tempfile.gettempdir()) / "profiles"


def summary_line(profile: Profile, from_cache: bool) -> str:
    """One line: the name, the sample count, the date range, and whether it came from the cache or the network."""
    source = "from cache" if from_cache else "from the network"
    return (
        f"{profile.name}: {len(profile.timestamps)} samples, {_stamp(profile.timestamps[0])} "
        f"to {_stamp(profile.timestamps[-1])}, {source}."
    )


class FetchWorker(QObject):
    """Runs one fetch. It lives on a worker thread and reports back through its signals only."""

    succeeded = pyqtSignal(object)  # FetchResult
    failed = pyqtSignal(str)
    ended = pyqtSignal()  # always the last signal, so the thread can quit

    def __init__(self, fetcher: ProfileFetcher, options: FetchOptions) -> None:
        super().__init__()
        self._fetcher = fetcher
        self._options = options
        self._cancelled = threading.Event()  # set from the UI thread, read here

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()

    def work(self) -> None:
        result: FetchResult | None = None
        message = ""
        try:
            result = self._fetcher.fetch(self._options)
        except FetchError as error:  # already logged at its level by the fetcher
            message = str(error)
        except Exception as error:  # shown on screen; an exception must not die silently in the thread
            log.error("Fetch failed unexpectedly: %s", error)
            message = f"unexpected error: {error}"
        try:
            if self.cancelled:
                log.info("Fetch cancelled: its result is discarded")
            elif result is not None:
                self.succeeded.emit(result)
            else:
                self.failed.emit(message)
        finally:
            self.ended.emit()


class FetchPanel(QGroupBox):
    """Fetch options, the Fetch and Cancel buttons, and the staged profile with its Use fetched profile button."""

    message = pyqtSignal(str, bool)  # text for the Setup message area; True when it reports a problem
    profile_chosen = pyqtSignal(object)  # Profile: the staged profile, chosen with Use fetched profile

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Fetch profile (NASA POWER)", parent)
        self._fetcher = ProfileFetcher(http_transport, default_cache_dir())
        self._thread: QThread | None = None
        self._worker: FetchWorker | None = None
        self._staged: Profile | None = None
        self._from_cache = False
        self._site = (0.0, 0.0)
        self._build()
        self._set_busy(False)

    @property
    def is_running(self) -> bool:
        return self._thread is not None

    @property
    def staged_profile(self) -> Profile | None:
        """The fetched profile waiting for Use fetched profile. It is not the active profile until chosen."""
        return self._staged

    def set_fetcher(self, fetcher: ProfileFetcher) -> None:
        """Fetch through fetcher from now on: a test passes one with a fake transport and a temporary cache."""
        if not self.is_running:
            self._fetcher = fetcher

    def set_site(self, latitude: float, longitude: float) -> None:
        """The Setup site position. Used by the fetch while Use Site location is checked."""
        self._site = (latitude, longitude)
        self._refresh_site_fields()

    def options(self) -> FetchOptions:
        """The fetch the controls describe."""
        if self.use_site_check.isChecked():
            latitude, longitude = self._site
        else:
            latitude, longitude = self.latitude_spin.value(), self.longitude_spin.value()
        return FetchOptions(
            latitude=latitude,
            longitude=longitude,
            start=_pydate(self.start_edit.date()),
            end=_pydate(self.end_edit.date()),
            irradiance=self.irradiance_box.currentData(),
            time_standard=self.standard_box.currentData(),
        )

    def start_fetch(self) -> None:
        """Fetch on a worker thread. Does nothing while a fetch is running."""
        if self.is_running:
            return
        self._thread = QThread(self)
        self._worker = FetchWorker(self._fetcher, self.options())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.work)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.ended.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._set_busy(True)
        self._thread.start()

    def cancel(self) -> None:
        """Discard the running fetch's result. The request itself finishes in the background."""
        if not self.is_running or self._worker.cancelled:
            return
        self._worker.cancel()
        self.cancel_button.setEnabled(False)
        self.status_label.setText(
            "Cancelling. The request finishes in the background and its result is discarded."
        )

    def use_fetched(self) -> None:
        """Make the staged profile the active one, through the Setup view."""
        if self._staged is not None and not self.is_running:
            self.profile_chosen.emit(self._staged)

    def shutdown(self) -> None:
        """End a running fetch before the window closes, so its thread is never destroyed while running.

        The UI thread waits here until the request returns, at most the 30 s timeout.
        """
        if self._thread is not None:
            self._worker.cancel()
            self._thread.quit()
            self._thread.wait()
            self._on_thread_finished()

    def _on_succeeded(self, result: FetchResult) -> None:
        self._staged = result.profile
        self._from_cache = result.from_cache
        self.status_label.setText(summary_line(result.profile, result.from_cache))
        self.message.emit(f"Fetched {result.profile.name}. Use fetched profile makes it active.", False)

    def _on_failed(self, text: str) -> None:
        self.status_label.setText(self._status_text())
        self.message.emit(f"Fetch failed: {text}. The active profile is unchanged.", True)

    def _on_thread_finished(self) -> None:
        cancelled = self._worker is not None and self._worker.cancelled
        self._thread = None
        self._worker = None
        self._set_busy(False)
        if cancelled:
            self.status_label.setText(self._status_text())
            self.message.emit("Fetch cancelled. Its result was discarded; the active profile is unchanged.", False)

    def _set_busy(self, busy: bool) -> None:
        self.fetch_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.use_button.setEnabled(not busy and self._staged is not None)
        self.progress.setVisible(busy)
        for widget in (self.use_site_check, self.start_edit, self.end_edit, self.irradiance_box, self.standard_box):
            widget.setEnabled(not busy)
        self._refresh_site_fields(busy)
        if busy:
            self.status_label.setText("Fetching from NASA POWER. Please wait; the rest of the window stays usable.")
        else:
            self.status_label.setText(self._status_text())

    def _refresh_site_fields(self, busy: bool | None = None) -> None:
        """While Use Site location is checked the position fields show the site and are disabled."""
        if busy is None:
            busy = self.is_running
        if self.use_site_check.isChecked():
            self.latitude_spin.setValue(self._site[0])
            self.longitude_spin.setValue(self._site[1])
        self.latitude_spin.setEnabled(not busy and not self.use_site_check.isChecked())
        self.longitude_spin.setEnabled(not busy and not self.use_site_check.isChecked())

    def _status_text(self) -> str:
        """The summary of the staged profile, or a hint when nothing has been fetched yet."""
        if self._staged is None:
            return "No fetched profile yet. Press Fetch to request one from NASA POWER."
        return summary_line(self._staged, self._from_cache)

    def _on_use_site_toggled(self, *_args) -> None:
        self._refresh_site_fields()

    def _on_fetch_clicked(self, *_args) -> None:
        self.start_fetch()

    def _on_cancel_clicked(self, *_args) -> None:
        self.cancel()

    def _on_use_clicked(self, *_args) -> None:
        self.use_fetched()

    def _build(self) -> None:
        self.use_site_check = QCheckBox("Use Site location")
        self.use_site_check.setChecked(True)
        self.use_site_check.toggled.connect(self._on_use_site_toggled)
        self.latitude_spin = _spin(-90.0, 90.0, 2, " °")
        self.longitude_spin = _spin(-180.0, 180.0, 2, " °")
        self.start_edit = _date_edit()
        self.end_edit = _date_edit()
        start, end = default_dates(date.today())
        self.start_edit.setDate(_qdate(start))
        self.end_edit.setDate(_qdate(end))
        self.irradiance_box = QComboBox()
        for label, value in IRRADIANCE_CHOICES:
            self.irradiance_box.addItem(label, value)
        self.standard_box = QComboBox()
        for label, value in STANDARD_CHOICES:
            self.standard_box.addItem(label, value)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy indicator: no known length
        self.progress.setVisible(False)
        self.status_label = QLabel(self._status_text())
        self.status_label.setWordWrap(True)

        self.fetch_button = QPushButton("Fetch")
        self.fetch_button.clicked.connect(self._on_fetch_clicked)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.use_button = QPushButton("Use fetched profile")
        self.use_button.clicked.connect(self._on_use_clicked)

        form = QFormLayout()
        form.addRow("Latitude", self.latitude_spin)
        form.addRow("Longitude", self.longitude_spin)
        form.addRow("Start date", self.start_edit)
        form.addRow("End date", self.end_edit)
        form.addRow("Irradiance", self.irradiance_box)
        form.addRow("Time standard", self.standard_box)

        buttons = QHBoxLayout()
        buttons.addWidget(self.fetch_button)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch(1)
        buttons.addWidget(self.use_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.use_site_check)
        layout.addLayout(form)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)


def _spin(low: float, high: float, decimals: int, suffix: str) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(low, high)
    spin.setDecimals(decimals)
    spin.setSingleStep(10.0**-decimals)
    spin.setSuffix(suffix)
    return spin


def _date_edit() -> QDateEdit:
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat(DATE_FORMAT)
    edit.setMaximumDate(QDate.currentDate())  # NASA POWER has no data for days still to come
    return edit


def _qdate(day: date) -> QDate:
    return QDate(day.year, day.month, day.day)


def _pydate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


def _stamp(stamp: np.datetime64) -> str:
    return np.datetime_as_string(stamp, unit="m").replace("T", " ")
