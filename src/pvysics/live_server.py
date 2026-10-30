"""The HTTP endpoint a device posts its readings to. Headless, no Qt, standard library only.

    POST /reading   a JSON object, or a JSON list of objects: one reading each (see live.parse_reading)
    GET  /status    {"listening": true}, to check the address and the token from the device

Every request must carry the token, as `Authorization: Bearer <token>` or `X-Api-Key: <token>`, because the
server listens on the network. The server only checks the request and hands each decoded body to `handler`, which
returns an IngestResult; what a reading means is not its business. It runs in its own thread.
"""

import hmac
import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)
MAX_BODY_BYTES = 64 * 1024
REQUEST_TIMEOUT_S = 10.0
READING_PATH = "/reading"
STATUS_PATH = "/status"


@dataclass(frozen=True)
class IngestResult:
    """What the handler did with a body: how many readings it took, and why it refused the others."""

    accepted: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)


Handler = Callable[[object], IngestResult]


class LiveServer:
    """Listens on host:port until stopped. Port 0 picks a free port; `port` then says which."""

    def __init__(self, handler: Handler, token: str, host: str = "0.0.0.0", port: int = 8765) -> None:
        if not token:
            raise ValueError("the live server needs a token")
        self._handler = handler
        self._token = token
        self._host = host
        self._requested_port = port
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._httpd is None:
            return self._requested_port
        return int(self._httpd.server_address[1])

    @property
    def is_listening(self) -> bool:
        return self._httpd is not None

    def start(self) -> None:
        """Start listening. Raises OSError if the port is taken or the address cannot be used."""
        if self._httpd is not None:
            return
        httpd = ThreadingHTTPServer((self._host, self._requested_port), _make_request_handler(self))
        httpd.daemon_threads = True
        self._httpd = httpd
        self._thread = threading.Thread(target=httpd.serve_forever, name="pvysics-live", daemon=True)
        self._thread.start()
        log.info("Live feed listening on %s:%d", self._host, self.port)

    def stop(self) -> None:
        httpd, thread = self._httpd, self._thread
        if httpd is None:
            return
        self._httpd = None
        self._thread = None
        httpd.shutdown()
        httpd.server_close()
        if thread is not None:
            thread.join(timeout=5.0)
        log.info("Live feed stopped")

    def _authorised(self, supplied: str) -> bool:
        return hmac.compare_digest(supplied.encode(), self._token.encode())

    def _ingest(self, body: object) -> IngestResult:
        return self._handler(body)


def _make_request_handler(server: LiveServer) -> type[BaseHTTPRequestHandler]:
    class Request(BaseHTTPRequestHandler):
        timeout = REQUEST_TIMEOUT_S  # a client that stalls cannot hold a thread for ever

        def do_GET(self) -> None:
            if self.path.split("?")[0] != STATUS_PATH:
                self._reply(404, {"error": f"not found: send readings with POST {READING_PATH}"})
            elif not self._token_ok():
                self._reply(401, {"error": "missing or wrong token"})
            else:
                self._reply(200, {"listening": True})

        def do_POST(self) -> None:
            if self.path.split("?")[0] != READING_PATH:
                self._reply(404, {"error": f"not found: send readings with POST {READING_PATH}"})
                return
            if not self._token_ok():
                self._reply(401, {"error": "missing or wrong token"})
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._reply(411, {"error": "send a Content-Length"})
                return
            if length < 0 or length > MAX_BODY_BYTES:
                self._reply(413, {"error": f"the body is larger than {MAX_BODY_BYTES} bytes"})
                return
            try:
                body = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                self._reply(400, {"error": "the body is not valid JSON"})
                return
            result = server._ingest(body)
            payload = {"accepted": result.accepted, "errors": list(result.errors)}
            if result.errors and result.accepted == 0:
                self._reply(422, payload)
            else:
                self._reply(202, payload)

        def _token_ok(self) -> bool:
            supplied = self.headers.get("X-Api-Key", "")
            bearer = self.headers.get("Authorization", "")
            if not supplied and bearer.lower().startswith("bearer "):
                supplied = bearer[7:].strip()
            return bool(supplied) and server._authorised(supplied)

        def _reply(self, status: int, payload: dict) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - the stdlib's signature
            log.debug("live feed request: " + format, *args)

    return Request
