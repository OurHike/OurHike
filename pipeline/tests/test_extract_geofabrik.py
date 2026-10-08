"""extract/_geofabrik.py: OSM's Geofabrik extracts kept in the raw store at most monthly, and the pin job's pull of them.

#1652 — Download OSM's Geofabrik extracts at most once a month, into a
private raw bucket that outlives the 7-day Actions cache. Every server is
requests_mock and every store a local directory under tmp_path; conftest.py's
socket guard stays on, so no extract is ever downloaded. The bodies are
invented bytes that open the way a PBF does (lib/geofabrik.py's
looks_like_pbf()), never a real extract.

The cases are the ones the issue and the dlt skill name: the change check
reads the store's own copies, FRESH inside the maximum age, STALE past it and
UNKNOWN with no copy, and never asks Geofabrik; a stale extract is streamed,
never held whole, into the store and named by its manifest row; and no
failed, refused or malformed download ever empties a state's copy. On the
build side, the pull holds each copy to the index, and a build with a missing
copy lands the last landed scans, or says it has none.
"""

import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import duckdb
import fsspec
import pytest

from extract import _geofabrik, _kinds
from extract._geofabrik import (
    CURRENT_PREFIX,
    INDEX_NAME,
    GeofabrikExtracts,
    bind_store,
    object_path,
    place_last_landed,
    pull_extracts,
    read_index,
    unbind_store,
    write_index,
)
from extract._run import make_pipeline, run_pipeline
from extract._warehouse import load_warehouse
from lib import geofabrik
from lib.freshness_state import Freshness
from lib.user_agent import USER_AGENT

BASE = "https://download.geofabrik.de/north-america/us"
ROBOTS = "https://download.geofabrik.de/robots.txt"
STATES = ("georgia", "maine")
NOW = datetime.now(UTC)


def pbf(size: int = 4096, seed: bytes = b"a") -> bytes:
    """Invented bytes in a PBF's opening shape: a 4-byte length, then a BlobHeader whose type is OSMHeader."""
    head = b"\x00\x00\x00\x0e\x0a\x09OSMHeader"
    return head + (seed * size)[: max(0, size - len(head))]


def url(state: str) -> str:
    return f"{BASE}/{geofabrik.extract_name(state)}"


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding the osm_water row's key and url, in place of the real one."""
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": [{"key": "osm_water", "url": f"{BASE}/", "kind": "geofabrik_extract"}]}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture
def store(tmp_path):
    """A local raw store bound as a running lane binds R2's: (filesystem, root)."""
    fs, root = fsspec.filesystem("file"), str(tmp_path / "raw-store")
    bind_store(fs, root)
    yield fs, root
    unbind_store()


@pytest.fixture
def naps(monkeypatch):
    """Every sleep, recorded and skipped: the crawl gap here and lib/http_retry.py's ladder both call time.sleep."""
    slept = []
    monkeypatch.setattr(_geofabrik.time, "sleep", slept.append)
    return slept


def resource(**overrides) -> GeofabrikExtracts:
    return GeofabrikExtracts(key="osm_water", club="osm", type="points_of_interest", states=STATES, **overrides)


def keep(fs, root, state: str, body: bytes, *, last_modified: datetime | None, pushed_at: datetime = NOW) -> dict:
    """Put a copy of `state` in the store and its entry in the index, as an earlier run would have."""
    key = GeofabrikExtracts.path(state)
    fs.makedirs(f"{root}/{CURRENT_PREFIX}/osm", exist_ok=True)
    with fs.open(object_path(root, key), "wb") as handle:
        handle.write(body)
    index = read_index(fs, root)
    index[key] = {
        "sha256": hashlib.sha256(body).hexdigest(),
        "size_bytes": len(body),
        "pushed_at": pushed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_key": "osm_water",
        "source_url": url(state),
        "last_modified": format_datetime(last_modified, usegmt=True) if last_modified else None,
        "etag": '"old"',
    }
    write_index(fs, root, index)
    return index[key]


def stored(fs, root, state: str) -> bytes:
    with fs.open(object_path(root, GeofabrikExtracts.path(state)), "rb") as handle:
        return handle.read()


def allow_all(requests_mock, delay: int | None = None):
    text = "User-agent: *\nDisallow:\n" + (f"Crawl-delay: {delay}\n" if delay is not None else "")
    requests_mock.get(ROBOTS, text=text)


# --- The change check: the store's own copies, never Geofabrik --------------------------------


def test_copies_younger_than_the_max_age_are_fresh_and_geofabrik_is_never_asked(registry, store, requests_mock):
    fs, root = store
    for state in STATES:
        keep(fs, root, state, pbf(), last_modified=NOW - timedelta(days=10))

    verdict, marker = resource().change_check(None)

    assert verdict is Freshness.FRESH
    assert requests_mock.call_count == 0, "a validator from a host that republishes daily always reads STALE"
    assert set(marker["copies"]) == set(STATES)


def test_a_copy_past_the_max_age_is_stale(registry, store, requests_mock):
    fs, root = store
    keep(fs, root, "georgia", pbf(), last_modified=NOW - timedelta(days=10))
    keep(fs, root, "maine", pbf(), last_modified=NOW - timedelta(days=30, minutes=1))

    assert resource().change_check(None)[0] is Freshness.STALE
    assert requests_mock.call_count == 0


def test_the_age_counts_from_the_copys_own_last_modified_not_from_when_it_was_stored(registry, store):
    """A copy stored yesterday of data Geofabrik dated 31 days ago is 31 days old: the date is the data's."""
    fs, root = store
    for state in STATES:
        keep(fs, root, state, pbf(), last_modified=NOW - timedelta(days=31), pushed_at=NOW - timedelta(days=1))

    assert resource().change_check(None)[0] is Freshness.STALE


def test_with_no_copy_the_check_is_unknown(registry, store):
    assert resource().change_check(None)[0] is Freshness.UNKNOWN


def test_an_index_entry_whose_object_is_missing_or_another_size_is_no_copy(registry, store):
    fs, root = store
    keep(fs, root, "georgia", pbf(), last_modified=NOW)
    keep(fs, root, "maine", pbf(), last_modified=NOW)
    fs.rm(object_path(root, GeofabrikExtracts.path("maine")))
    assert resource().change_check(None)[0] is Freshness.UNKNOWN

    keep(fs, root, "maine", pbf(), last_modified=NOW)
    with fs.open(object_path(root, GeofabrikExtracts.path("maine")), "wb") as handle:
        handle.write(pbf(100))  # replaced behind the index's back
    assert resource().change_check(None)[0] is Freshness.UNKNOWN


def test_outside_a_run_no_store_is_bound_and_the_resource_is_unavailable_rather_than_empty(registry):
    from extract._contract import Unavailable

    with pytest.raises(Unavailable):
        resource().change_check(None)


# --- The read: streamed into the store, never emptied --------------------------------------


class Recorded(io.BytesIO):
    """A response body that records the size of every read, to show the download streamed rather than read whole."""

    def __init__(self, data: bytes):
        super().__init__(data)
        self.reads: list[int] = []

    def read(self, size=-1):
        self.reads.append(size)
        return super().read(size)


def test_a_stale_extract_is_streamed_into_the_store_and_its_row_names_the_copy(registry, store, requests_mock, naps):
    fs, root = store
    keep(fs, root, "maine", pbf(seed=b"m"), last_modified=NOW - timedelta(days=3))
    body = pbf(3 * (1 << 20) + 17, seed=b"g")
    streamed = Recorded(body)
    allow_all(requests_mock)
    requests_mock.get(
        url("georgia"),
        body=streamed,
        headers={"Content-Length": str(len(body)), "Last-Modified": "Fri, 02 Oct 2026 20:43:11 GMT", "ETag": '"g1"'},
    )
    proofs = {}

    rows = {row["state"]: row for row in resource().rows(proofs)}

    assert stored(fs, root, "georgia") == body
    assert len(streamed.reads) > 3 and max(streamed.reads) <= 1 << 20, "read in chunks of at most 1 MiB, never whole"
    assert rows["georgia"]["sha256"] == hashlib.sha256(body).hexdigest() and rows["georgia"]["read_this_run"] is True
    assert rows["georgia"]["last_modified"] == "Fri, 02 Oct 2026 20:43:11 GMT" and rows["georgia"]["etag"] == '"g1"'
    assert rows["maine"]["read_this_run"] is False, "a copy inside its max age is not downloaded again"
    assert [request.url for request in requests_mock.request_history] == [ROBOTS, url("georgia")]
    assert {request.headers["User-Agent"] for request in requests_mock.request_history} == {USER_AGENT}
    assert proofs == {"raw_osm__osm_water": 2}
    assert read_index(fs, root)["osm/georgia-latest.osm.pbf"]["sha256"] == rows["georgia"]["sha256"]


def test_a_failed_download_keeps_the_last_copy_and_its_row_says_why(registry, store, requests_mock, naps):
    """The dlt skill's rule 2, second half: one failed download never empties a source's water."""
    fs, root = store
    old = pbf(seed=b"o")
    before = keep(fs, root, "georgia", old, last_modified=NOW - timedelta(days=40))
    keep(fs, root, "maine", pbf(seed=b"m"), last_modified=NOW - timedelta(days=40))
    allow_all(requests_mock)
    requests_mock.get(url("georgia"), status_code=503)
    requests_mock.get(url("maine"), content=pbf(seed=b"n"))

    rows = {row["state"]: row for row in resource().rows({})}

    assert stored(fs, root, "georgia") == old and read_index(fs, root)["osm/georgia-latest.osm.pbf"] == before
    assert rows["georgia"]["read_this_run"] is False and "503" in rows["georgia"]["read_error"]
    assert rows["maine"]["read_this_run"] is True and stored(fs, root, "maine") == pbf(seed=b"n")


def test_a_body_that_is_not_a_pbf_or_is_cut_short_never_replaces_a_copy(registry, store, requests_mock, naps):
    fs, root = store
    old = pbf(seed=b"o")
    for state in STATES:
        keep(fs, root, state, old, last_modified=NOW - timedelta(days=40))
    allow_all(requests_mock)
    requests_mock.get(url("georgia"), text="<html>Service unavailable</html>")
    requests_mock.get(url("maine"), content=pbf(100), headers={"Content-Length": "5000"})

    rows = {row["state"]: row for row in resource().rows({})}

    assert stored(fs, root, "georgia") == old and stored(fs, root, "maine") == old
    assert "OSMHeader" in rows["georgia"]["read_error"] and "Content-Length" in rows["maine"]["read_error"]


def test_a_state_that_never_landed_and_fails_has_no_row_rather_than_an_empty_one(registry, store, requests_mock, naps):
    """Absent means unknown (CLAUDE.md): a row with no copy behind it would read as a copy."""
    fs, root = store
    keep(fs, root, "maine", pbf(), last_modified=NOW)
    allow_all(requests_mock)
    requests_mock.get(url("georgia"), status_code=404)
    proofs = {}

    rows = list(resource().rows(proofs))

    assert [row["state"] for row in rows] == ["maine"] and proofs == {"raw_osm__osm_water": 1}


def test_robots_txt_that_disallows_the_extracts_asks_for_none_of_them(registry, store, requests_mock, naps):
    fs, root = store
    old = pbf()
    keep(fs, root, "georgia", old, last_modified=NOW - timedelta(days=40))
    requests_mock.get(ROBOTS, text=f"User-agent: {USER_AGENT.split('/')[0]}\nDisallow: /north-america/\n")

    rows = list(resource().rows({}))

    assert [request.url for request in requests_mock.request_history] == [ROBOTS]
    assert stored(fs, root, "georgia") == old and "not asked" in rows[0]["read_error"]


def test_a_robots_txt_that_cannot_be_read_refuses_everything_and_a_404_is_no_rules(registry, store, requests_mock, naps):
    """RFC 9309: a server error or no answer is unreachable, read as disallow (2.3.1.4); a 4xx is no rules (2.3.1.3)."""
    requests_mock.get(ROBOTS, status_code=503)
    assert list(resource().rows({})) == [] and requests_mock.call_count == 3, "robots.txt is retried, never the extracts"

    requests_mock.reset_mock()
    requests_mock.get(ROBOTS, status_code=404)
    for state in STATES:
        requests_mock.get(url(state), content=pbf())
    assert {row["state"] for row in resource().rows({})} == set(STATES)


def test_the_crawl_delay_is_waited_between_two_downloads(registry, store, requests_mock, naps):
    allow_all(requests_mock, delay=7)
    for state in STATES:
        requests_mock.get(url(state), content=pbf())

    list(resource().rows({}))

    assert len([nap for nap in naps if nap > 6]) == 2, "before each download, the host's own Crawl-delay"


def test_a_spent_download_budget_starts_no_more_downloads(registry, store, requests_mock, naps, monkeypatch):
    monkeypatch.setattr(_geofabrik, "DOWNLOAD_BUDGET_SECONDS", -1)
    allow_all(requests_mock)

    rows = list(resource().rows({}))

    assert rows == [] and [request.url for request in requests_mock.request_history] == [ROBOTS]


def test_the_registry_row_names_the_directory_lib_geofabrik_downloads_from():
    """Two homes of one URL (sources.json's osm_water row and lib/geofabrik.py), held equal."""
    _kinds._registry.cache_clear()
    assert _kinds.registry_entry("osm_water")["url"].rstrip("/") == geofabrik.GEOFABRIK_BASE


# --- The monthly lane, end to end ---------------------------------------------------------


def test_the_monthly_lane_lands_one_row_per_extract_and_a_rerun_inside_the_max_age_downloads_nothing(
    registry, tmp_path, requests_mock, naps
):
    bucket_url, pipelines = (tmp_path / "raw-store").as_uri(), str(tmp_path / "pipelines")
    allow_all(requests_mock)
    for state in STATES:
        requests_mock.get(
            url(state), content=pbf(seed=state[:1].encode()), headers={"Last-Modified": format_datetime(NOW, usegmt=True)}
        )

    first = run_pipeline("monthly", bucket_url, resources=[resource()], pipelines_dir=pipelines)
    asked = requests_mock.call_count
    second = run_pipeline("monthly", bucket_url, resources=[resource()], pipelines_dir=pipelines)

    assert first.verdicts == {"raw_osm__osm_water": "unknown"} and second.verdicts == {"raw_osm__osm_water": "fresh"}
    assert requests_mock.call_count == asked == 3, "robots.txt and two extracts, once"
    con = duckdb.connect()
    load_warehouse(con, make_pipeline("monthly", bucket_url, pipelines))
    landed = con.execute("select state, read_this_run from raw.raw_osm__osm_water order by state").fetchall()
    assert landed == [("georgia", True), ("maine", True)]
    with pytest.raises(Exception, match="no raw store is bound"):
        _geofabrik.bound_store()  # the run unbinds what it bound


# --- The build side -----------------------------------------------------------------------


def test_the_pull_holds_each_copy_to_the_index_and_a_moved_one_is_unreadable(registry, store, tmp_path):
    fs, root = store
    for state in STATES:
        keep(fs, root, state, pbf(seed=state[:1].encode()), last_modified=NOW)
    with fs.open(object_path(root, GeofabrikExtracts.path("maine")), "wb") as handle:
        handle.write(pbf(seed=b"x"))  # same size, other bytes
    raw = tmp_path / "raw"

    pulled = pull_extracts(fs, root, raw, STATES)

    assert pulled.states["georgia"] == "ok" and pulled.states["maine"].startswith("unreadable")
    assert pulled.extracts == "partial"
    assert (raw / "osm" / "georgia-latest.osm.pbf").read_bytes() == pbf(seed=b"g")
    assert sorted(path.name for path in (raw / "osm").iterdir()) == ["georgia-latest.osm.pbf"], "no part file left"


def pin(fs, steps: str, raw_run: str, scans: dict[str, bytes], *, finished: bool = True) -> None:
    """An earlier build's pin, holding these water scans under as_landed/, its manifest last."""
    landed = {}
    for path, body in scans.items():
        fs.makedirs(f"{steps}/raw_inputs/{raw_run}/as_landed/{Path(path).parent}", exist_ok=True)
        with fs.open(f"{steps}/raw_inputs/{raw_run}/as_landed/{path}", "wb") as handle:
            handle.write(body)
        landed[path] = {"table": None, "load_id": None, "sha256": hashlib.sha256(body).hexdigest()}
    if finished:
        with fs.open(f"{steps}/raw_inputs/{raw_run}/raw_inputs.json", "w") as handle:
            handle.write(json.dumps({"raw_run": raw_run, "as_landed": landed}))


def test_the_last_landed_scans_come_from_the_newest_earlier_finished_pin_that_holds_each(tmp_path):
    fs, steps, raw = fsspec.filesystem("file"), str(tmp_path / "steps"), tmp_path / "raw"
    points = b'{"type": "FeatureCollection", "features": [{"type": "Feature"}]}'
    sites = b'{"sites": [{"water": {}}, {"water": null}]}'
    pin(fs, steps, "20260801T051500.000000Z", {"derived/osm_water.geojson": b"older", "derived/trail_water.json": sites})
    pin(fs, steps, "20260903T051500.000000Z", {"derived/osm_water.geojson": points})
    pin(fs, steps, "20260920T051500.000000Z", {"derived/osm_water.geojson": b"unfinished"}, finished=False)
    pin(fs, steps, "20261103T051500.000000Z", {"derived/osm_water.geojson": b"later than this build"})

    placed = place_last_landed(fs, steps, "20261003T051500.000000Z", raw)

    assert placed["derived/osm_water.geojson"]["raw_run"] == "20260903T051500.000000Z"
    assert placed["derived/trail_water.json"]["raw_run"] == "20260801T051500.000000Z"
    assert (raw / "osm_water.geojson").read_bytes() == points and (raw / "trail_water.json").read_bytes() == sites


def test_a_build_with_no_copy_and_no_earlier_scan_warns_and_says_it_publishes_no_osm_water(registry, tmp_path, capsys):
    summary, output = tmp_path / "summary.md", tmp_path / "output"
    argv = [
        "pull",
        "--bucket-url",
        (tmp_path / "raw-store").as_uri(),
        "--steps-url",
        (tmp_path / "steps").as_uri(),
        "--raw-run",
        "20261003T051500.000000Z",
        "--raw-dir",
        str(tmp_path / "raw"),
        "--summary",
        str(summary),
        "--github-output",
        str(output),
    ]

    assert _geofabrik.main(argv) == 0

    assert output.read_text() == "extracts=none\n"
    assert "No OSM water and no site water this build" in summary.read_text()
    assert "::warning title=No OSM water this build::" in capsys.readouterr().out


def test_landed_says_which_scan_the_build_lands_and_warns_when_a_complete_set_kept_the_last_one(tmp_path, capsys):
    raw = tmp_path / "raw"
    (raw / "osm").mkdir(parents=True)
    kept = b'{"type": "FeatureCollection", "features": []}'
    (raw / "osm_water.geojson").write_bytes(kept)
    (raw / "trail_water.json").write_text('{"sites": [{"water": {"m": 1}}, {"water": null}]}')
    record = {
        "extracts": "complete",
        "scans": {
            "derived/osm_water.geojson": {"raw_run": "20260903T051500.000000Z", "sha256": hashlib.sha256(kept).hexdigest()}
        },
    }
    (raw / "osm" / _geofabrik.PULL_RECORD).write_text(json.dumps(record))

    assert _geofabrik.main(["landed", "--raw-dir", str(raw), "--summary", str(tmp_path / "summary.md")]) == 0

    page = (tmp_path / "summary.md").read_text()
    assert "the last landed scan, from raw_run `20260903T051500.000000Z`, 0 points" in page
    assert "`derived/trail_water.json`: this build's scan of the extracts, 1 of 2 sites with water" in page
    assert "kept from raw_run 20260903T051500.000000Z" in capsys.readouterr().out


def test_the_pin_paths_the_pin_job_writes_are_the_ones_build_marts_lands_and_the_scanners_write():
    """One list, three readers: refresh-reference.yml's pin step (its pin job's, since choice B moved the build to
    build-reference.yml), build_marts.py's monthly lane and the two scanners."""
    import yaml

    import build_marts
    import fetch_osm_water
    import fetch_trail_water

    lane = {
        step.name: dict(step.lane_args)["monthly"]
        for step in build_marts.STEPS
        if step.name in ("step_osm_water", "step_site_water")
    }
    assert {args[1].removeprefix("{raw_dir}/") for args in lane.values()} == set(_geofabrik.SCANS)
    assert set(_geofabrik.SCANS.values()) == {fetch_osm_water.OUT_PATH.name, fetch_trail_water.OUT_PATH.name}
    assert fetch_osm_water.OUT_PATH.parent == fetch_trail_water.OUT_PATH.parent == fetch_trail_water.RAW_DIR
    workflow = Path(build_marts.__file__).parent.parent / ".github" / "workflows" / "refresh-reference.yml"
    steps = yaml.safe_load(workflow.read_text())["jobs"]["pin"]["steps"]
    (pin,) = [step for step in steps if "extract._warehouse pin " in (step.get("run") or "")]
    for pinned, local in _geofabrik.SCANS.items():
        assert f"--extra {pinned}=data/raw/{local}" in pin["run"]


def test_the_index_is_never_a_key_the_mirror_holds_and_keys_cannot_leave_their_prefix(tmp_path):
    root = str(tmp_path)
    with pytest.raises(ValueError, match="index"):
        object_path(root, INDEX_NAME)
    for key in ("../escape.pbf", "osm//georgia.pbf", "/osm/georgia.pbf", "osm/geor gia.pbf"):
        with pytest.raises(ValueError, match="not a raw-store key"):
            object_path(root, key)
    assert object_path(root, "osm/georgia-latest.osm.pbf") == f"{root}/current/osm/georgia-latest.osm.pbf"


def test_an_extract_redirected_to_another_host_keeps_the_last_copy_and_its_row_says_why(registry, store, requests_mock, naps):
    """Review finding SEC-5 of PR #1805: the download used bare requests, outside the session that refuses another
    host's answer, so a moved extract would have been stored from a host whose robots.txt nobody read."""
    fs, root = store
    old = pbf(seed=b"o")
    keep(fs, root, "georgia", old, last_modified=NOW - timedelta(days=40))
    keep(fs, root, "maine", pbf(seed=b"m"), last_modified=NOW - timedelta(days=3))
    allow_all(requests_mock)
    elsewhere = "https://mirror.example.net/georgia-latest.osm.pbf"
    requests_mock.get(url("georgia"), status_code=302, headers={"Location": elsewhere})
    requests_mock.get(elsewhere, content=pbf(seed=b"x"))

    rows = {row["state"]: row for row in resource().rows({})}

    assert stored(fs, root, "georgia") == old, "the other host's bytes never replace the copy"
    assert rows["georgia"]["read_this_run"] is False and "another host" in rows["georgia"]["read_error"]
