"""The HTTP endpoint: authorisation, bodies, status codes. Headless: a real socket on a free local port."""

import json
import urllib.error
import urllib.request

import pytest

from pvysics.live_server import MAX_BODY_BYTES, IngestResult, LiveServer

TOKEN = "s3cret-token"


@pytest.fixture
def served():
    """A server on a free local port whose handler records what it was given."""
    received: list[object] = []

    def handler(body: object) -> IngestResult:
        received.append(body)
        items = body if isinstance(body, list) else [body]
        bad = [item for item in items if not isinstance(item, dict) or "g" not in item]
        return IngestResult(accepted=len(items) - len(bad), errors=tuple("no g" for _ in bad))

    server = LiveServer(handler, TOKEN, host="127.0.0.1", port=0)
    server.start()
    yield server, received
    server.stop()


def call(server, path="/reading", method="POST", body=None, headers=None, raw=None):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    request = urllib.request.Request(f"http://127.0.0.1:{server.port}{path}", data=data, method=method)
    for key, value in ({"X-Api-Key": TOKEN} if headers is None else headers).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_a_reading_with_the_token_is_accepted_and_handed_to_the_handler(served):
    server, received = served

    status, reply = call(server, body={"g": 640, "t": 32})

    assert status == 202
    assert reply == {"accepted": 1, "errors": []}
    assert received == [{"g": 640, "t": 32}]


def test_the_token_may_come_as_a_bearer_header(served):
    server, received = served

    status, _ = call(server, body={"g": 1}, headers={"Authorization": f"Bearer {TOKEN}"})

    assert status == 202 and len(received) == 1


def test_a_list_of_readings_is_accepted_in_one_post(served):
    server, received = served

    status, reply = call(server, body=[{"g": 1}, {"g": 2}, {"x": 3}])

    assert status == 202  # two were taken, so the post is not a failure
    assert reply["accepted"] == 2 and reply["errors"] == ["no g"]


def test_a_post_where_every_reading_is_refused_is_a_422(served):
    server, _ = served

    status, reply = call(server, body={"x": 1})

    assert status == 422 and reply["accepted"] == 0


@pytest.mark.parametrize("headers", [{}, {"X-Api-Key": "wrong"}, {"Authorization": "Bearer wrong"}, {"X-Api-Key": ""}])
def test_a_missing_or_wrong_token_is_refused_and_nothing_is_handled(served, headers):
    server, received = served

    post_status, _ = call(server, body={"g": 1}, headers=headers)
    get_status, _ = call(server, path="/status", method="GET", headers=headers)

    assert (post_status, get_status) == (401, 401)
    assert received == []


def test_status_tells_a_device_the_address_and_token_work(served):
    server, _ = served

    assert call(server, path="/status", method="GET") == (200, {"listening": True})


def test_bad_bodies_and_paths_get_plain_errors(served):
    server, received = served

    assert call(server, raw=b"not json")[0] == 400
    assert call(server, raw=b"x" * (MAX_BODY_BYTES + 1))[0] == 413
    assert call(server, path="/elsewhere", body={"g": 1})[0] == 404
    assert received == []


def test_stopping_closes_the_port_and_the_server_can_start_again(served):
    server, _ = served
    port = server.port

    server.stop()

    assert not server.is_listening
    with pytest.raises(OSError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=1)
    server.start()
    assert server.is_listening


def test_a_taken_port_is_an_oserror_so_the_app_can_say_so(served):
    server, _ = served
    second = LiveServer(lambda body: IngestResult(), TOKEN, host="127.0.0.1", port=server.port)

    with pytest.raises(OSError):
        second.start()


def test_a_server_needs_a_token():
    with pytest.raises(ValueError):
        LiveServer(lambda body: IngestResult(), "")
