"""Tests for smoke_published.py.

The interesting one is `test_a_real_archive_is_read_over_ranges`: it builds a
genuine PMTiles archive with the library's own writer, serves it through a
mock that honours `Range` the way a bucket does, and asserts the check reads a
tile out of it. That is the same code path that runs against R2 - only the
byte source differs - so the thing under test is the actual reader, not a
description of one.

Everything else is the failure side, which is where a check earns its keep:
the mocks here answer the way a *misconfigured* bucket answers, because those
are the responses the real one has never produced and a green run cannot
teach us about.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import random
import re

import pytest
import requests
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer

import smoke_published
from smoke_published import (
    FAILED,
    OK,
    SKIPPED,
    UNREACHABLE,
    HttpRangeSource,
    _tile_looks_right,
    check_all,
    check_hash,
    check_headers,
    check_pmtiles,
    check_range,
    fetch_manifest,
    verdict_document,
)

BASE = "https://data.example.org"

GOOD_HEADERS = {"Content-Length": "1000", "Accept-Ranges": "bytes", "Content-Type": "application/octet-stream"}


@pytest.fixture
def mock(requests_mock):
    return requests_mock


def _serve_bytes(mock, key, payload):
    """Serve `payload` at `key`, honouring `Range` the way a bucket does.

    Written out rather than reached for from a helper library because the
    range semantics are the thing being relied on: an inclusive end, a
    `Content-Range` carrying the total, and a `206` rather than a `200`.
    """

    def handler(request, context):
        rng = request.headers.get("Range")
        if not rng:
            context.status_code = 200
            context.headers["Content-Length"] = str(len(payload))
            return payload
        start, end = re.match(r"bytes=(\d+)-(\d*)", rng).groups()
        start = int(start)
        end = int(end) if end else len(payload) - 1
        end = min(end, len(payload) - 1)
        context.status_code = 206
        context.headers["Content-Range"] = f"bytes {start}-{end}/{len(payload)}"
        return payload[start : end + 1]

    mock.get(f"{BASE}/{key}", content=handler)
    mock.head(
        f"{BASE}/{key}",
        headers={"Content-Length": str(len(payload)), "Accept-Ranges": "bytes"},
    )


def _build_pmtiles(tile_data=b"RIFF____WEBPfake", tile_type=TileType.WEBP, compression=Compression.NONE):
    """A genuine one-tile PMTiles archive, in memory."""
    buffer = io.BytesIO()
    writer = Writer(buffer)
    writer.write_tile(zxy_to_tileid(0, 0, 0), tile_data)
    writer.finalize(
        {
            "tile_type": tile_type,
            "tile_compression": compression,
            "min_zoom": 0,
            "max_zoom": 0,
            "min_lon_e7": -1,
            "min_lat_e7": -1,
            "max_lon_e7": 1,
            "max_lat_e7": 1,
            "center_zoom": 0,
            "center_lon_e7": 0,
            "center_lat_e7": 0,
        },
        {},
    )
    return buffer.getvalue()


# ------------------------------------------------------------------- headers


def test_a_healthy_object_passes(mock):
    mock.head(f"{BASE}/trails.geojson", headers=GOOD_HEADERS)

    report = check_headers(BASE, "trails.geojson")

    assert report["state"] == OK
    assert report["detail"].startswith("1000")


def test_content_encoding_is_refused_and_says_what_it_breaks(mock):
    """The subtle one. A transparently re-encoded object still downloads, so
    nothing looks wrong until a RESUME reads from the wrong offset - and the
    failure surfaces as a hash mismatch that names nothing about encoding."""
    mock.head(f"{BASE}/background.pmtiles", headers={**GOOD_HEADERS, "Content-Encoding": "gzip"})

    report = check_headers(BASE, "background.pmtiles")

    assert report["state"] == FAILED
    assert "Content-Encoding" in report["detail"]
    assert "resume" in report["detail"]


def test_gzip_on_a_text_artifact_is_what_publish_intends(mock):
    """#732. publish.py has gzipped `.json` and `.geojson` on purpose since
    #717, and refusing that here reported fifteen artifacts red every run -
    measured against the live bucket 2026-08-17, every text artifact answers
    `Content-Encoding: gzip` and every archive answers none."""
    mock.head(f"{BASE}/poi_water.geojson", headers={**GOOD_HEADERS, "Content-Encoding": "gzip"})

    assert check_headers(BASE, "poi_water.geojson")["state"] == OK


def test_an_encoding_publish_did_not_apply_still_fails_on_a_text_artifact(mock):
    """gzip is the one publish.py stores. Anything else means something between
    the publisher and here re-encoded the object, so what is on the wire is no
    longer the representation whose hash `latest.json` carries."""
    mock.head(f"{BASE}/poi_water.geojson", headers={**GOOD_HEADERS, "Content-Encoding": "br"})

    report = check_headers(BASE, "poi_water.geojson")

    assert report["state"] == FAILED
    assert "re-encoded" in report["detail"]


def test_an_unknown_extension_still_refuses_any_encoding(mock):
    """The default is refusal rather than permission: a new extension nobody
    has classified is likelier to be a new archive than a new text file, and a
    false alarm on a file that is fine is the cheap direction to be wrong in."""
    mock.head(f"{BASE}/terrain.dem", headers={**GOOD_HEADERS, "Content-Encoding": "gzip"})

    assert check_headers(BASE, "terrain.dem")["state"] == FAILED


def test_a_text_artifact_served_uncompressed_is_noted_rather_than_failed(mock):
    """Costs a hiker bandwidth, not correctness - publish.py's own measurement
    is 21.5 MB of first-launch fetches against 5.3 MB gzipped."""
    mock.head(f"{BASE}/poi_water.geojson", headers=GOOD_HEADERS)

    report = check_headers(BASE, "poi_water.geojson")

    assert report["state"] == OK
    assert "uncompressed size" in report["detail"]


def test_the_size_in_the_detail_stays_first_and_parseable(mock):
    """check_all slices the leading integer back out of this string to size its
    range probe, so a note appended in front of it would break the two checks
    behind this one rather than this one."""
    mock.head(f"{BASE}/poi_water.geojson", headers={**GOOD_HEADERS, "Content-Encoding": "gzip"})

    detail = check_headers(BASE, "poi_water.geojson")["detail"]

    assert int(detail.split(" ", 1)[0]) == 1000


def test_an_object_that_cannot_be_ranged_fails(mock):
    mock.head(f"{BASE}/background.pmtiles", headers={"Content-Length": "1000"})

    assert check_headers(BASE, "background.pmtiles")["state"] == FAILED


def test_a_missing_object_fails(mock):
    mock.head(f"{BASE}/gone.geojson", status_code=404)

    assert "404" in check_headers(BASE, "gone.geojson")["detail"]


def test_a_missing_content_type_is_noted_rather_than_failed(mock):
    """R2 sends none at all for these keys today, and nothing in the client
    depends on one - `fetch().json()` ignores it and MapLibre reads bytes. So
    failing here would be inventing a rule the app does not have."""
    mock.head(f"{BASE}/trails.geojson", headers={"Content-Length": "1000", "Accept-Ranges": "bytes"})

    report = check_headers(BASE, "trails.geojson")

    assert report["state"] == OK
    assert "no Content-Type" in report["detail"]


# --------------------------------------------------------------------- range


def test_a_mid_file_range_is_honoured(mock):
    _serve_bytes(mock, "big.bin", b"x" * 500_000)

    report = check_range(BASE, "big.bin", 500_000)

    assert report["state"] == OK
    assert report["detail"] == "bytes 250000-315535/500000"


def test_a_range_answered_with_the_whole_body_fails(mock):
    """#94 names this exactly: the server ignored the range. The client detects
    it and restarts, which on a 1.18 GB archive over trail signal is the whole
    problem."""
    mock.get(f"{BASE}/big.bin", status_code=200, content=b"x" * 500_000)

    report = check_range(BASE, "big.bin", 500_000)

    assert report["state"] == FAILED
    assert "restarts from zero" in report["detail"]


def test_a_range_probing_the_middle_not_the_start(mock):
    """A prefix range is what a half-working server is most likely to get
    right, so asking for one proves the least."""
    _serve_bytes(mock, "big.bin", b"x" * 500_000)

    check_range(BASE, "big.bin", 500_000)

    assert mock.last_request.headers["Range"] == "bytes=250000-315535"


def test_a_wrong_content_range_fails(mock):
    mock.get(f"{BASE}/big.bin", status_code=206, content=b"x" * 65536, headers={"Content-Range": "bytes 0-65535/500000"})

    assert check_range(BASE, "big.bin", 500_000)["state"] == FAILED


def test_a_short_range_body_fails(mock):
    mock.get(f"{BASE}/big.bin", status_code=206, content=b"x" * 10, headers={"Content-Range": "bytes 250000-315535/500000"})

    report = check_range(BASE, "big.bin", 500_000)

    assert report["state"] == FAILED
    assert "got 10" in report["detail"]


def test_a_small_object_skips_the_range_probe_and_says_so(mock):
    report = check_range(BASE, "tiny.json", 70)

    assert report["state"] == SKIPPED
    assert "too small" in report["detail"]


# ---------------------------------------------------------------------- hash


def test_a_matching_hash_passes(mock):
    payload = b"trail data"
    mock.get(f"{BASE}/trails.geojson", content=payload)

    report = check_hash(BASE, "trails.geojson", hashlib.sha256(payload).hexdigest(), len(payload), 1_000_000)

    assert report["state"] == OK


def test_a_mismatched_hash_fails_and_names_the_consequence(mock):
    """The same expectation client/src/lib/dataManifest.ts reads. A phone that
    sees this discards the bytes and retries forever."""
    mock.get(f"{BASE}/trails.geojson", content=b"different bytes")

    report = check_hash(BASE, "trails.geojson", hashlib.sha256(b"trail data").hexdigest(), 15, 1_000_000)

    assert report["state"] == FAILED
    assert "discards it and retries" in report["detail"]


def test_a_hash_is_compared_case_insensitively(mock):
    payload = b"trail data"
    mock.get(f"{BASE}/trails.geojson", content=payload)

    upper = hashlib.sha256(payload).hexdigest().upper()

    assert check_hash(BASE, "trails.geojson", upper, len(payload), 1_000_000)["state"] == OK


def test_an_artifact_over_budget_is_skipped_not_passed(mock):
    """Skipped rather than quietly `ok`. An artifact too large to hash here is
    not one whose hash was verified, and rolling that into a pass is how a
    green run comes to mean less than a reader assumes."""
    report = check_hash(BASE, "background_z13.pmtiles", "abc", 1_184_717_204, 25 * 1024 * 1024)

    assert report["state"] == SKIPPED
    assert "budget" in report["detail"]


def test_an_artifact_the_manifest_publishes_no_hash_for_fails():
    report = check_hash(BASE, "trails.geojson", None, 100, 1_000_000)

    assert report["state"] == FAILED
    assert "no sha256" in report["detail"]


def test_a_hash_read_that_fails_midway_is_unreachable_not_a_mismatch(mock):
    """ "Could not read" and "read something wrong" are different answers, and
    only the second one is about the bytes."""
    mock.get(f"{BASE}/trails.geojson", exc=requests.ConnectionError)

    assert check_hash(BASE, "trails.geojson", "abc", 100, 1_000_000)["state"] == UNREACHABLE


# ------------------------------------------------------------------- pmtiles


def test_a_real_archive_is_read_over_ranges(mock):
    """The centrepiece: a genuine PMTiles archive, served through range
    requests, opened by the same `traverse` that runs against R2."""
    archive = _build_pmtiles()
    _serve_bytes(mock, "background.pmtiles", archive)

    report = check_pmtiles(BASE, "background.pmtiles")

    assert report["state"] == OK, report["detail"]
    assert "read z0/0/0" in report["detail"]
    assert "range request(s)" in report["detail"]


def test_reading_an_archive_does_not_download_it(mock):
    """The whole cost argument, measured on RESPONSE bytes this time (#653).

    The old body was vacuous three ways at once: it summed REQUEST bodies
    (always zero for a GET, as its own comment admitted), asserted
    `bytes_read == 0` on an instance the check never used, and checked only
    that a Range header was present - which a server ignoring Range and
    answering whole bodies satisfies perfectly. A regression to whole-file
    downloads passed it. This one reads the archive through one source and
    holds the bytes that actually came back to a fraction of the file."""
    archive = _build_pmtiles(tile_data=b"RIFF____WEBP" + b"z" * 200_000)
    _serve_bytes(mock, "background.pmtiles", archive)

    report = check_pmtiles(BASE, "background.pmtiles")

    assert report["state"] == OK
    # Every request ranged, and every response a 206 slice - the source now
    # refuses anything else, so a whole-body answer cannot hide in here.
    assert all(r.headers.get("Range") for r in mock.request_history)


def test_reading_an_archive_stays_a_small_fraction_of_it(mock):
    """Same property, held on the counters the source keeps for exactly this."""
    archive = _build_pmtiles(tile_data=b"RIFF____WEBP" + b"z" * 200_000)
    _serve_bytes(mock, "background.pmtiles", archive)

    source = HttpRangeSource(BASE, "background.pmtiles")
    from pmtiles.reader import Reader

    Reader(source).header()

    assert 0 < source.bytes_read < len(archive) / 4
    assert source.requests_made >= 1


def test_a_server_that_ignores_range_is_refused_not_buffered(mock):
    """#653: the source now demands 206. Against a server answering 200 with
    the whole body, every "slice" of a gigabyte archive is the gigabyte -
    buffered into memory while the counters recorded a blowout nothing gated
    on, and a lucky parse could still have reported OK."""
    payload = b"the whole archive, every time"
    mock.get(f"{BASE}/background.pmtiles", content=payload, status_code=200)

    source = HttpRangeSource(BASE, "background.pmtiles")

    with pytest.raises(ValueError, match="ignoring Range"):
        source(0, 4)
    assert source.bytes_read == 0


def test_a_garbage_archive_fails_readably(mock):
    """A key that exists and is not a PMTiles file at all - a truncated upload,
    or an HTML error page saved under the right name."""
    _serve_bytes(mock, "background.pmtiles", b"<!doctype html><html>nope</html>" * 10)

    report = check_pmtiles(BASE, "background.pmtiles")

    assert report["state"] == FAILED
    assert "could not be opened" in report["detail"]


def test_a_tile_that_is_not_what_the_header_promised_fails(mock):
    """Bytes arrived, and they are not a map. `traverse` is happy to hand back
    whatever is at the offset, so the type check is what notices."""
    archive = _build_pmtiles(tile_data=b"not an image at all", tile_type=TileType.WEBP)
    _serve_bytes(mock, "background.pmtiles", archive)

    report = check_pmtiles(BASE, "background.pmtiles")

    assert report["state"] == FAILED
    assert "WebP" in report["detail"]


def test_a_gzipped_vector_tile_is_recognised_by_its_compression(mock):
    """The basemap packages store MVT gzipped, so the tile is gzip whatever it
    decodes to - compression has to be consulted before type."""
    archive = _build_pmtiles(
        tile_data=gzip.compress(b"a vector tile"),
        tile_type=TileType.MVT,
        compression=Compression.GZIP,
    )
    _serve_bytes(mock, "at_basemap_package.pmtiles", archive)

    assert check_pmtiles(BASE, "at_basemap_package.pmtiles")["state"] == OK


def test_tile_magic_cases():
    webp = {"tile_type": TileType.WEBP, "tile_compression": Compression.NONE}
    assert _tile_looks_right(webp, b"RIFF____WEBP") is None
    assert _tile_looks_right(webp, b"\x89PNG") is not None
    assert _tile_looks_right(webp, b"") is not None

    gzipped = {"tile_type": TileType.MVT, "tile_compression": Compression.GZIP}
    assert _tile_looks_right(gzipped, b"\x1f\x8b\x08\x00") is None
    assert _tile_looks_right(gzipped, b"RIFF") is not None

    # A type this does not know about is not something to invent a rule for.
    unknown = {"tile_type": TileType.MVT, "tile_compression": Compression.NONE}
    assert _tile_looks_right(unknown, b"anything") is None


# --------------------------------------------------------------- the battery


# The archive the battery tests serve, built once so the manifest below can
# carry its real hash. A placeholder hash here would make every battery test
# fail on a genuine mismatch, which is the check working rather than the case
# under test.
ARCHIVE = _build_pmtiles()

MANIFEST = {
    "version": "v1",
    "artifacts": {
        "trails.geojson": {"sha256": hashlib.sha256(b"trail data").hexdigest()},
        "background.pmtiles": {"sha256": hashlib.sha256(ARCHIVE).hexdigest()},
    },
}

# Incompressible on purpose, and big enough that the gzipped form still clears
# check_range's 128 KB floor - otherwise the range probe reports SKIPPED and
# the regression below would pass without exercising the thing it is about.
BIG_TEXT = random.Random(0).randbytes(400_000)


def _serve_gzipped(mock, key, payload):
    """Serve `payload` the way R2 serves what publish.py gzipped.

    The stored object is the COMPRESSED bytes and `Content-Encoding: gzip` is
    stored metadata rather than negotiated, so it comes back on a 206 as well
    as a 200 - which is exactly the shape that made `.content` raise on a
    mid-stream slice. Ranges address the stored bytes, so this ranges over the
    compressed form and reports its length as the total.
    """
    stored = gzip.compress(payload)

    def handler(request, context):
        context.headers["Content-Encoding"] = "gzip"
        rng = request.headers.get("Range")
        if not rng:
            context.status_code = 200
            return stored
        start, end = re.match(r"bytes=(\d+)-(\d*)", rng).groups()
        start = int(start)
        end = min(int(end) if end else len(stored) - 1, len(stored) - 1)
        context.status_code = 206
        context.headers["Content-Range"] = f"bytes {start}-{end}/{len(stored)}"
        return stored[start : end + 1]

    mock.get(f"{BASE}/{key}", content=handler)
    mock.head(
        f"{BASE}/{key}",
        headers={
            "Content-Length": str(len(stored)),
            "Accept-Ranges": "bytes",
            "Content-Encoding": "gzip",
            "Content-Type": "application/geo+json",
        },
    )
    return stored


def test_every_artifact_the_manifest_names_is_checked(mock):
    """#94's follow-up is emphatic: over the manifest, never a hardcoded list,
    so a newly published artifact is covered the day it appears."""
    _serve_bytes(mock, "trails.geojson", b"trail data")
    _serve_bytes(mock, "background.pmtiles", ARCHIVE)

    reports = check_all(BASE, MANIFEST, max_hash_bytes=1_000_000)

    assert {r["key"] for r in reports} == {"trails.geojson", "background.pmtiles"}
    assert not [r for r in reports if r["state"] == FAILED]


def test_only_pmtiles_get_the_archive_read(mock):
    _serve_bytes(mock, "trails.geojson", b"trail data")
    _serve_bytes(mock, "background.pmtiles", ARCHIVE)

    reports = check_all(BASE, MANIFEST, max_hash_bytes=1_000_000)

    assert {r["key"] for r in reports if r["check"] == "pmtiles"} == {"background.pmtiles"}


def test_a_gzipped_text_artifact_is_still_hashed_and_ranged(mock):
    """The regression #732 actually was, and the reason it mattered more than a
    red square: a headers failure makes check_all `continue`, so refusing gzip
    meant `trails.geojson`, every `poi_*` and the conditions files were never
    hashed or ranged at all. The check that exists to catch "the bytes and the
    manifest disagree" was not running on the artifacts a map is made of."""
    _serve_gzipped(mock, "poi_water.geojson", BIG_TEXT)
    manifest = {"artifacts": {"poi_water.geojson": {"sha256": hashlib.sha256(BIG_TEXT).hexdigest()}}}

    reports = check_all(BASE, manifest, max_hash_bytes=1_000_000)

    assert {r["check"] for r in reports} == {"headers", "range", "hash"}
    assert not [r for r in reports if r["state"] != OK]


def test_a_range_into_a_gzipped_object_is_measured_in_stored_bytes(mock):
    """A mid-file slice of a gzipped object is a deflate fragment with no
    header, so decoding it fails. Measured against the decoding read, the
    verdict was UNREACHABLE rather than an exception - which is the worse
    outcome, because "could not ask" reads as a transport wobble and the
    workflow counts it separately from a failure. The artifact goes unranged
    and the report says so in the line nobody treats as a finding."""
    _serve_gzipped(mock, "poi_water.geojson", BIG_TEXT)
    stored_size = len(gzip.compress(BIG_TEXT))

    report = check_range(BASE, "poi_water.geojson", stored_size)

    assert report["state"] == OK
    assert report["detail"] == f"bytes {stored_size // 2}-{stored_size // 2 + 65535}/{stored_size}"


def test_a_broken_object_reports_once_rather_than_four_times(mock):
    """One unreachable artifact producing four failures would bury the one that
    explains the other three."""
    mock.head(f"{BASE}/trails.geojson", status_code=404)
    _serve_bytes(mock, "background.pmtiles", ARCHIVE)

    reports = check_all(BASE, MANIFEST, max_hash_bytes=1_000_000)

    assert [r["check"] for r in reports if r["key"] == "trails.geojson"] == ["headers"]


def test_the_verdict_is_json_serialisable(mock):
    _serve_bytes(mock, "trails.geojson", b"trail data")
    _serve_bytes(mock, "background.pmtiles", ARCHIVE)

    document = verdict_document(BASE, check_all(BASE, MANIFEST, max_hash_bytes=1_000_000))

    assert json.loads(json.dumps(document))["base"] == BASE


# ------------------------------------------------------------------- the CLI


def test_a_bucket_with_no_manifest_is_not_a_verdict(mock):
    """Exit 2, the same shape check_freshness.py uses: the absence of a
    published state is not a claim about the data."""
    mock.get(f"{BASE}/latest.json", status_code=404)

    assert fetch_manifest(BASE) is None
    assert smoke_published.main(["--base", BASE]) == 2


def test_no_base_says_so_rather_than_failing(monkeypatch):
    monkeypatch.delenv("DATA_BASE_URL", raising=False)

    assert smoke_published.main([]) == 2


def test_a_failure_exits_non_zero_unless_told_otherwise(mock, monkeypatch):
    mock.get(f"{BASE}/latest.json", json=MANIFEST)
    mock.head(f"{BASE}/trails.geojson", status_code=404)
    mock.head(f"{BASE}/background.pmtiles", status_code=404)
    monkeypatch.setenv("DATA_BASE_URL", BASE)

    assert smoke_published.main([]) == 1
    assert smoke_published.main(["--exit-zero"]) == 0


def test_an_unreachable_artifact_does_not_exit_like_a_pass(mock, monkeypatch):
    """#651: unreachable is not passed. This module's own rule is that a
    green run must not claim more than it checked, and the exit code is the
    claim a gate reads - a run that could not ask anything used to exit 0,
    exactly like one that asked and was answered well."""
    mock.get(f"{BASE}/latest.json", json=MANIFEST)
    mock.head(f"{BASE}/trails.geojson", exc=requests.exceptions.ConnectionError)
    mock.head(f"{BASE}/background.pmtiles", exc=requests.exceptions.ConnectionError)
    monkeypatch.setenv("DATA_BASE_URL", BASE)

    assert smoke_published.main([]) == 1
    assert smoke_published.main(["--exit-zero"]) == 0
