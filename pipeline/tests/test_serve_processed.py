"""serve_processed.py's Range and CORS behaviour, against a real server (#324).

The module's whole purpose is the two things `http.server` does not do -
byte ranges and CORS with Content-Range exposed - and both break silently:
a served client falls back to downloading whole archives, or the browser
hides the header and pmtiles cannot tell whether its range was honoured.
It is also the documented way to test the client's offline download locally,
so a regression here costs a debugging session on the wrong side of the
seam. Tested against a real HTTPServer on a loopback port (which the
conftest network guard deliberately leaves open): the range arithmetic is
the subject, and exercising it through a mocked handler would re-implement
the thing under test.
"""

from __future__ import annotations

import threading
from functools import partial
from http.server import HTTPServer

import pytest
import requests

from serve_processed import RangeRequestHandler

BODY = bytes(range(256)) * 4  # 1,024 distinguishable bytes


@pytest.fixture
def served(tmp_path):
    (tmp_path / "archive.pmtiles").write_bytes(BODY)
    handler = partial(RangeRequestHandler, directory=str(tmp_path))
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/archive.pmtiles"
    finally:
        server.shutdown()
        thread.join()


def test_a_plain_get_answers_200_with_the_cors_surface(served):
    response = requests.get(served, timeout=5)

    assert response.status_code == 200
    assert response.content == BODY
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert "Content-Range" in response.headers["Access-Control-Expose-Headers"]
    assert response.headers["Accept-Ranges"] == "bytes"


def test_a_bounded_range_answers_206_with_exactly_those_bytes(served):
    response = requests.get(served, headers={"Range": "bytes=10-19"}, timeout=5)

    assert response.status_code == 206
    assert response.content == BODY[10:20]
    assert response.headers["Content-Range"] == f"bytes 10-19/{len(BODY)}"
    assert response.headers["Content-Length"] == "10"


def test_an_open_ended_range_runs_to_the_end(served):
    response = requests.get(served, headers={"Range": "bytes=1000-"}, timeout=5)

    assert response.status_code == 206
    assert response.content == BODY[1000:]
    assert response.headers["Content-Range"] == f"bytes 1000-{len(BODY) - 1}/{len(BODY)}"


def test_an_end_past_the_file_is_clamped_not_erred(served):
    response = requests.get(served, headers={"Range": "bytes=1000-999999"}, timeout=5)

    assert response.status_code == 206
    assert response.content == BODY[1000:]


def test_a_start_past_the_file_is_416_carrying_the_real_size(served):
    """The 416 has to carry the size - that is how a client that guessed too
    far learns what to ask for instead."""
    response = requests.get(served, headers={"Range": f"bytes={len(BODY)}-"}, timeout=5)

    assert response.status_code == 416
    assert response.headers["Content-Range"] == f"bytes */{len(BODY)}"


def test_a_suffix_range_is_rejected_rather_than_half_implemented(served):
    # Valid HTTP, never sent by pmtiles, and the module refuses it by design.
    response = requests.get(served, headers={"Range": "bytes=-500"}, timeout=5)

    assert response.status_code == 400


def test_a_range_for_a_missing_file_is_404(served):
    response = requests.get(served.replace("archive", "ghost"), headers={"Range": "bytes=0-9"}, timeout=5)

    assert response.status_code == 404


def test_preflight_answers_204_with_range_allowed(served):
    response = requests.options(served, timeout=5)

    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Headers"] == "Range"
