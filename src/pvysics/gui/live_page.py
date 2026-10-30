"""The Live page: start and stop the feed a device posts its readings to, see how it is going, and how to send.

The device (an ESP32 or a logger) POSTs one JSON reading at a time to this computer. The page holds the settings
(port, who may connect, how long a silence counts as no data), the token a device must send, and shows the address
and an example to copy. The readings go to the same Dashboard, Trends, Data and Event Log pages a simulated run uses.
"""

import json
import logging
import socket
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from pvysics.gui.live_controller import MAX_TIMEOUT_S, MIN_TIMEOUT_S, FeedStatus
from pvysics.gui.simple_pages import card, card_header, colour_text, page_header, page_layout
from pvysics.gui.ui_helpers import role_label
from pvysics.live_server import READING_PATH

if TYPE_CHECKING:
    from pvysics.gui.session import Session

log = logging.getLogger(__name__)
EXAMPLE_READING = {"g": 640.0, "t": 32.5, "v": 29.0, "i": 5.2}
NONE_YET = "-"
SPIN_MAX_WIDTH_PX = 200


def local_addresses() -> list[str]:
    """This computer's IPv4 addresses a device on the network could reach, the likeliest first."""
    found: list[str] = []
    try:  # the address the computer would use to reach the network: no packet is sent
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 1))
            found.append(probe.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in found and not address.startswith("127."):
                found.append(address)
    except OSError:
        pass
    return found or ["127.0.0.1"]


class LivePage(QWidget):
    """Settings, token, instructions and status of the live feed."""

    def __init__(self, session: "Session") -> None:
        super().__init__()
        self._session = session
        self._live = session.live

        self.port_spin = QSpinBox()
        self.port_spin.setRange(0, 65535)
        self.port_spin.setSpecialValueText("Automatic")
        self.port_spin.setValue(self._live.port)
        self.port_spin.setToolTip("The port devices send to. Automatic lets the system choose; the address below then shows it.")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(MIN_TIMEOUT_S, MAX_TIMEOUT_S)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setValue(self._live.timeout_s)
        self.timeout_spin.setToolTip("After this long without a reading the Dashboard shows NO DATA.")
        for spin in (self.port_spin, self.timeout_spin):
            spin.setMaximumWidth(SPIN_MAX_WIDTH_PX)
        self.network_check = QCheckBox("Accept readings from other devices on the network")
        self.network_check.setChecked(self._live.accept_network)
        self.network_check.setToolTip("Off: only this computer can send. On: an ESP32 on the same network can too. The token is always required.")
        self.token_edit = QLineEdit(self._live.token)
        self.token_edit.setReadOnly(True)
        self.copy_button = QPushButton("Copy token")
        self.new_token_button = QPushButton("New token")
        self.new_token_button.setToolTip("Make a new token. Devices must be given it, and a running feed uses it after a restart.")
        self.start_button = QPushButton("START LISTENING")
        self.start_button.setProperty("variant", "primary")
        self.stop_button = QPushButton("STOP")

        form = QFormLayout()
        form.addRow("Port", self.port_spin)
        form.addRow("No data after", self.timeout_spin)
        form.addRow("", self.network_check)
        token_row = QHBoxLayout()
        token_row.addWidget(self.token_edit, 1)
        token_row.addWidget(self.copy_button)
        token_row.addWidget(self.new_token_button)
        form.addRow("Token", token_row)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        buttons.addStretch(1)
        listen_card = card(
            card_header("Listen", "The feed a device sends its readings to."),
            form,
            buttons,
        )

        self.how_text = QPlainTextEdit()
        self.how_text.setReadOnly(True)
        self.how_text.setMinimumHeight(270)
        self.how_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = self.how_text.font()
        font.setFamily("monospace")
        font.setStyleHint(font.StyleHint.Monospace)
        self.how_text.setFont(font)
        send_card = card(card_header("Send readings to", "One reading, or a list of readings, as JSON."), self.how_text)

        self.message_label = role_label("", "cardSub")
        self.message_label.setWordWrap(True)
        self.status_value = role_label(FeedStatus.STOPPED.value, "kpi")
        self.counts_label = role_label("", "cardSub")
        self.last_label = role_label("", "cardSub")
        self.problem_label = role_label("", "cardSub")
        self.problem_label.setWordWrap(True)
        self.log_label = role_label("", "cardSub")
        self.log_label.setWordWrap(True)
        self.log_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        status_card = card(
            card_header("Status"),
            self.status_value,
            self.counts_label,
            self.last_label,
            self.problem_label,
            self.log_label,
            self.message_label,
        )

        layout = page_layout(self)
        layout.addLayout(page_header("Live Feed", "Readings from an ESP32 or a logger, scored as they arrive."))
        layout.addWidget(listen_card)
        layout.addWidget(send_card)
        layout.addWidget(status_card)
        layout.addStretch(1)

        self.start_button.clicked.connect(self._on_start_clicked)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.copy_button.clicked.connect(self._on_copy_clicked)
        self.new_token_button.clicked.connect(self._on_new_token_clicked)
        self.port_spin.valueChanged.connect(self._refresh_how)
        self.token_edit.textChanged.connect(self._refresh_how)
        self._live.active_changed.connect(self._refresh)
        self._live.status_changed.connect(self._refresh)
        self._live.counts_changed.connect(self._refresh)
        session.theme.changed.connect(lambda _palette: self._refresh())
        self._refresh()

    @property
    def example_text(self) -> str:
        return self.how_text.toPlainText()

    def _settings(self) -> None:
        self._live.configure(self.port_spin.value(), self.timeout_spin.value(), self.network_check.isChecked())

    def _on_start_clicked(self, *_args) -> None:
        self._settings()
        try:
            self._live.start()
        except OSError as error:
            self.message_label.setText(f"Could not listen on port {self.port_spin.value() or 'automatic'}: {error.strerror or error}")
            log.warning("Live feed could not start: %s", error)
            return
        self.message_label.setText("")
        if self.port_spin.value() == 0:
            self.port_spin.setValue(self._live.listening_port)  # show the port the system chose
        self._refresh()

    def _on_stop_clicked(self, *_args) -> None:
        self._live.stop()

    def _on_copy_clicked(self, *_args) -> None:
        QApplication.clipboard().setText(self._live.token)
        self.message_label.setText("Token copied.")

    def _on_new_token_clicked(self, *_args) -> None:
        self.token_edit.setText(self._live.new_token())
        running = " The running feed keeps the old token until it is restarted." if self._live.is_active else ""
        self.message_label.setText("New token made. Give it to your devices." + running)

    def _refresh(self, *_args) -> None:
        live = self._live
        active = live.is_active
        self.start_button.setEnabled(not active)
        self.stop_button.setEnabled(active)
        for widget in (self.port_spin, self.timeout_spin, self.network_check):
            widget.setEnabled(not active)
        self.status_value.setText(live.status.value)
        palette = self._session.theme.palette
        colour_text(self.status_value, palette.muted_text if live.status in (FeedStatus.STOPPED, FeedStatus.WAITING) else None)
        self.counts_label.setText(f"{live.accepted} readings accepted · {live.rejected} refused")
        self.last_label.setText(f"Last reading: {live.last_reading_text or NONE_YET}")
        self.problem_label.setText(f"Last problem: {live.last_error}" if live.last_error else "")
        self.log_label.setText(f"Readings are kept in {live.log_path}" if live.log_path else "")
        self._refresh_how()

    def _refresh_how(self, *_args) -> None:
        port = self._live.listening_port if self._live.is_active else self.port_spin.value()
        token = self._live.token if self._live.is_active else self.token_edit.text()
        port_text = str(port) if port else "<port>"
        addresses = local_addresses() if self.network_check.isChecked() else ["127.0.0.1"]
        body = json.dumps(EXAMPLE_READING)
        lines = ["Send to (use the address that is on your device's network):"]
        lines += [f"  http://{address}:{port_text}{READING_PATH}" for address in addresses]
        lines += [
            "",
            f"Header:   X-Api-Key: {token}",
            "Method:   POST, Content-Type: application/json",
            "",
            f"Body:     {body}",
            "          g irradiance W/m2, t module temperature C, v volts, i amps",
            "          (or power in W instead of v and i; time is optional, as 2025-01-15T10:00:00)",
            "",
            "Try it from a terminal:",
            f"  curl -X POST http://{addresses[0]}:{port_text}{READING_PATH} \\",
            f"       -H 'X-Api-Key: {token}' -H 'Content-Type: application/json' -d '{body}'",
        ]
        self.how_text.setPlainText("\n".join(lines))
