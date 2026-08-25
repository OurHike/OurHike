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

from serve_processed import MANIFEST_KEY, RangeRequestHandler, build_manifest

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


# --- The synthesized manifest (#950) --------------------------------------
#
# Since #197 the client checks every artifact it draws against its published
# sha256, and publish.py writes that manifest into the BUCKET, not into
# data/processed/. Most artifacts read an absent hash as the pre-#197
# downgrade and draw anyway; the nearby-trail network does not, because
# unverifiable trail lines are a trail drawn where the trail is not. So
# without this the one map that most needs reviewing before it is published
# is the one that cannot be looked at locally.


@pytest.fixture
def served_root(tmp_path):
    """A processed directory with an artifact, a sidecar and a subdirectory."""
    (tmp_path / "nearby_trails.geojson").write_bytes(b'{"type":"FeatureCollection","features":[]}')
    (tmp_path / "nearby_trails_manifest.json").write_bytes(b'{"path":"x","sha256":"y"}')
    (tmp_path / "conditions").mkdir()
    (tmp_path / "conditions" / "closures.json").write_bytes(b"[]")
    handler = partial(RangeRequestHandler, directory=str(tmp_path))
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield tmp_path, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join()


def test_the_manifest_hashes_what_is_actually_on_disk(served_root):
    import hashlib

    root, base = served_root
    body = (root / "nearby_trails.geojson").read_bytes()

    answered = requests.get(f"{base}/{MANIFEST_KEY}", timeout=5).json()

    assert answered["artifacts"]["nearby_trails.geojson"]["sha256"] == hashlib.sha256(body).hexdigest()


def test_the_manifest_key_is_the_bucket_key_including_a_prefix(served_root):
    # The bucket key IS the relative path, which is why this needs no second
    # copy of publish.py's key logic - and `conditions/` is the one prefix
    # that would expose a flat-name shortcut.
    _, base = served_root

    artifacts = requests.get(f"{base}/{MANIFEST_KEY}", timeout=5).json()["artifacts"]

    assert "conditions/closures.json" in artifacts


def test_the_manifest_omits_the_pipelines_own_bookkeeping(served_root):
    # `*_manifest.json` sidecars are how the exports talk to publish.py. No
    # client fetches one, and listing them would invite somebody to think the
    # bucket serves them.
    _, base = served_root

    artifacts = requests.get(f"{base}/{MANIFEST_KEY}", timeout=5).json()["artifacts"]

    assert "nearby_trails_manifest.json" not in artifacts


def test_a_real_manifest_on_disk_wins(served_root):
    # Serving a directory copied out of the bucket has to behave exactly as
    # the bucket did, or this tool stops being a rehearsal.
    root, base = served_root
    (root / MANIFEST_KEY).write_text('{"artifacts": {"only": {"sha256": "from-disk"}}}')

    answered = requests.get(f"{base}/{MANIFEST_KEY}", timeout=5).json()

    assert answered == {"artifacts": {"only": {"sha256": "from-disk"}}}


def test_an_archive_too_large_to_hash_is_left_out_rather_than_stalling_the_server(tmp_path, monkeypatch):
    # A 1.18 GB PMTiles archive re-hashed on every manifest request would make
    # the dev server unusable, and imagery is exactly the artifact whose
    # absent hash is harmless - the client reads it as "no published hash",
    # which is the state it was already in.
    import serve_processed

    monkeypatch.setattr(serve_processed, "MAX_HASHED_BYTES", 8)
    (tmp_path / "small.json").write_bytes(b"12345")
    (tmp_path / "background.pmtiles").write_bytes(b"far too many bytes to hash")

    artifacts = build_manifest(tmp_path)["artifacts"]

    assert "small.json" in artifacts
    assert "background.pmtiles" not in artifacts


def test_a_re_export_is_not_served_its_old_hash(tmp_path):
    # The cache is keyed on (path, mtime, size), so bytes that change cannot
    # keep vouching for themselves under the old digest - which on this
    # server would mean the client refusing to draw a freshly exported map.
    import hashlib
    import os

    artifact = tmp_path / "nearby_trails.geojson"
    artifact.write_bytes(b"first export")
    first = build_manifest(tmp_path)["artifacts"]["nearby_trails.geojson"]["sha256"]

    artifact.write_bytes(b"a second, different export")
    # Explicit rather than incidental: a same-second rewrite is exactly the
    # case a coarser cache key would get wrong, and re-running an export
    # twice in one second is a normal thing to do.
    os.utime(artifact, ns=(0, 0))

    second = build_manifest(tmp_path)["artifacts"]["nearby_trails.geojson"]["sha256"]

    assert first == hashlib.sha256(b"first export").hexdigest()
    assert second == hashlib.sha256(b"a second, different export").hexdigest()
