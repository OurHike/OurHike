"""prepare_closure_trail_lines.py reads a release's trail lines once, into the file the hourly cut of area closures reads.

Decision 187 (S6, the maintainer's poll of 2026-10-11): the hourly build crosses out an area closure's trails where they run
inside it, and these are its lines: the release's nearby trail lines and, since decision 192 (the maintainer's poll of
2026-10-14, "Yes, like any trail"), the A.T.'s own trails.geojson. No test here touches the network: latest.json and the
downloads are stubbed.
"""

import hashlib
import json

import duckdb
import pytest

import prepare_closure_trail_lines as prepare

LINE_A = {"type": "LineString", "coordinates": [[-73.9700004, 41.03], [-73.97, 41.035]]}
LINE_B = {"type": "MultiLineString", "coordinates": [[[-74.2, 41.2], [-74.2, 41.25]], [[-74.21, 41.2], [-74.21, 41.21]]]}
LINE_C = {"type": "LineString", "coordinates": [[-120.0, 45.0], [-120.0, 45.01]]}
#: An A.T. centerline chain as trails.geojson carries one, through Bear Mountain's ground.
AT_LINE = {"type": "LineString", "coordinates": [[-73.99, 41.31], [-73.98, 41.32]]}


def _feature(feature_id, geometry, **properties):
    return {"type": "Feature", "properties": {"id": feature_id, "source": "oprhp_trails", **properties}, "geometry": geometry}


def _write(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def _rows(out_dir):
    with duckdb.connect() as con:
        return con.execute(
            f"select release, line_id, xmin, ymin, xmax, ymax, geometry, source "
            f"from read_parquet('{out_dir / prepare.LINES_FILE}')"
        ).fetchall()


def _nearby(tmp_path, features):
    return {prepare.NEARBY_KEY: _write(tmp_path / prepare.NEARBY_KEY, features)}


def test_each_line_lands_once_with_its_box_at_the_phone_files_five_decimals_ordered_by_place(tmp_path):
    sources = {
        prepare.NEARBY_KEY: _write(
            tmp_path / prepare.NEARBY_KEY, [_feature("b", LINE_B), _feature("a", LINE_A), _feature("c", LINE_C)]
        ),
        prepare.AT_KEY: _write(
            tmp_path / prepare.AT_KEY, [_feature("centerline:chain:0", AT_LINE, source="centerline", blaze_color="White")]
        ),
    }

    document = prepare.prepare(
        sources,
        tmp_path / "out",
        release="2026-10-10-2",
        environment="ua",
        source_sha256s={prepare.NEARBY_KEY: "x", prepare.AT_KEY: "y"},
    )

    rows = _rows(tmp_path / "out")
    assert [row[1] for row in rows] == ["c", "b", "centerline:chain:0", "a"], (
        "west to east, so neighbouring lines compress together, whichever file each came from"
    )
    release, line_id, xmin, ymin, xmax, ymax, geometry, source = rows[3]
    assert (release, line_id, source) == ("2026-10-10-2", "a", prepare.NEARBY_KEY)
    assert json.loads(geometry) == {"type": "LineString", "coordinates": [[-73.97, 41.03], [-73.97, 41.035]]}
    assert (xmin, ymin, xmax, ymax) == (-73.97, 41.03, -73.97, 41.035)
    assert json.loads(rows[1][6])["type"] == "MultiLineString"
    assert rows[2][7] == prepare.AT_KEY
    assert document == {
        "schema": 2,
        "environment": "ua",
        "release": "2026-10-10-2",
        "sources": {
            prepare.NEARBY_KEY: {"sha256": "x", "lines": 3},
            prepare.AT_KEY: {"sha256": "y", "lines": 1},
        },
        "lines": 4,
        "vertices": 10,
    }
    assert json.loads((tmp_path / "out" / prepare.RELEASE_FILE).read_text()) == document
    assert sources[prepare.NEARBY_KEY].exists() and sources[prepare.AT_KEY].exists()


def test_the_release_artifacts_read_are_every_line_a_phone_draws_the_at_among_them():
    """Decision 192: the A.T.'s own trails.geojson beside the nearby trail lines, and a schema past the one that held
    no A.T. line, so a file prepared before the decision is never read as one prepared after it."""
    assert prepare.SOURCE_KEYS == ("nearby_trails.geojson", "trails.geojson")
    assert prepare.SCHEMA >= 2


def test_one_row_per_line_id_whatever_the_release_holds(tmp_path):
    """A shared id is told apart by each line's own geometry, an exact copy is written once, and a line with no id is
    named by its geometry, so stg_derived__closure_trail_lines' key and its source's exactness test cannot fail."""
    sources = _nearby(
        tmp_path,
        [
            _feature("twin", LINE_A),
            _feature("twin", LINE_C),
            _feature("copy", LINE_B),
            _feature("copy", LINE_B),
            _feature(None, LINE_C),
        ],
    )

    prepare.prepare(sources, tmp_path / "out", release="r", environment=None, source_sha256s=None)

    ids = [row[1] for row in _rows(tmp_path / "out")]
    assert len(ids) == len(set(ids)) == 4
    assert "copy" in ids
    assert sorted(line_id.split("#")[0] for line_id in ids if line_id.startswith("twin")) == ["twin", "twin"]
    assert any(line_id.startswith("geometry:") for line_id in ids)


def test_one_row_per_line_id_across_the_two_files(tmp_path):
    """An id both files use is told apart by geometry, and a line both files carry whole is written once."""
    sources = {
        prepare.NEARBY_KEY: _write(tmp_path / prepare.NEARBY_KEY, [_feature("shared", LINE_A), _feature("same", LINE_C)]),
        prepare.AT_KEY: _write(tmp_path / prepare.AT_KEY, [_feature("shared", AT_LINE), _feature("same", LINE_C)]),
    }

    document = prepare.prepare(sources, tmp_path / "out", release="r", environment=None, source_sha256s=None)

    ids = [row[1] for row in _rows(tmp_path / "out")]
    assert len(ids) == len(set(ids)) == 3
    assert ids.count("same") == 1
    assert sorted(line_id.split("#")[0] for line_id in ids if line_id.startswith("shared")) == ["shared", "shared"]
    assert document["lines"] == 3


def test_what_is_not_a_line_or_collapses_at_five_decimals_is_left_out(tmp_path):
    sources = _nearby(
        tmp_path,
        [
            _feature("point", {"type": "Point", "coordinates": [-74.0, 41.0]}),
            _feature("short", {"type": "LineString", "coordinates": [[-74.25, 41.205], [-74.250001, 41.205]]}),
            _feature("kept", LINE_C),
        ],
    )

    document = prepare.prepare(sources, tmp_path / "out", release="r", environment=None, source_sha256s=None)

    assert [row[1] for row in _rows(tmp_path / "out")] == ["kept"]
    assert document["lines"] == 1


class _Response:
    def __init__(self, document):
        self.document = document

    def json(self):
        return self.document


def _latest(release, sha256s):
    return {
        "release": release,
        "artifacts": {key: {"sha256": sha256, "size_bytes": 1} for key, sha256 in sha256s.items()},
    }


@pytest.fixture
def served(tmp_path, monkeypatch):
    """latest.json and the release's two line files as a bucket would serve them, and every download counted."""
    bodies = {
        prepare.NEARBY_KEY: _write(tmp_path / "served_nearby.geojson", [_feature("a", LINE_A)]).read_bytes(),
        prepare.AT_KEY: _write(tmp_path / "served_at.geojson", [_feature("centerline:chain:0", AT_LINE)]).read_bytes(),
    }
    sha256s = {key: hashlib.sha256(body).hexdigest() for key, body in bodies.items()}
    state = {"latest": _latest("2026-10-10-2", sha256s), "downloads": [], "bodies": bodies, "sha256s": sha256s}

    def request(url, **_):
        assert url == "https://data.example/environments/ua/latest.json"
        return _Response(state["latest"])

    def download(url, dest, **kwargs):
        assert kwargs["headers"]["User-Agent"].startswith("OurHike")
        state["downloads"].append(url)
        dest.write_bytes(bodies[url.rsplit("/", 1)[1]])
        return dest

    monkeypatch.setattr(prepare, "request_with_retry", request)
    monkeypatch.setattr(prepare, "download_with_retry", download)
    monkeypatch.setenv("DATA_BASE_URL", "https://data.example")
    return state


RELEASE_URL = "https://data.example/environments/ua/releases/2026-10-10-2"


def test_a_release_is_downloaded_once_and_prepared_once(tmp_path, served):
    out = tmp_path / "out"

    assert prepare.main(["--env", "ua", "--out-dir", str(out)]) == 0
    assert served["downloads"] == [f"{RELEASE_URL}/nearby_trails.geojson", f"{RELEASE_URL}/trails.geojson"]
    held = prepare.prepared(out)
    assert held["release"] == "2026-10-10-2"
    assert {key: entry["sha256"] for key, entry in held["sources"].items()} == served["sha256s"]
    assert [row[1] for row in _rows(out)] == ["centerline:chain:0", "a"], "the A.T.'s line is prepared beside the nearby one"

    assert prepare.main(["--env", "ua", "--out-dir", str(out)]) == 0
    assert len(served["downloads"]) == 2, "a release already prepared is not read again"


def test_a_directory_prepared_under_another_schema_is_prepared_again(tmp_path, served):
    """A cache restored from before decision 192 held no A.T. line: its schema is refused, so it is read again."""
    out = tmp_path / "out"
    prepare.main(["--env", "ua", "--out-dir", str(out)])
    held = json.loads((out / prepare.RELEASE_FILE).read_text())
    (out / prepare.RELEASE_FILE).write_text(json.dumps({**held, "schema": 1}))

    assert prepare.prepared(out) is None
    assert prepare.main(["--env", "ua", "--out-dir", str(out)]) == 0
    assert len(served["downloads"]) == 4
    assert prepare.prepared(out)["schema"] == prepare.SCHEMA


def test_the_squares_steps_copies_are_taken_when_they_are_the_releases_bytes(tmp_path, served):
    reuse = tmp_path / "release"
    reuse.mkdir()
    for key, body in served["bodies"].items():
        (reuse / key).write_bytes(body)

    assert prepare.main(["--env", "ua", "--out-dir", str(tmp_path / "out"), "--reuse-dir", str(reuse)]) == 0
    assert served["downloads"] == []


def test_only_the_file_the_squares_step_does_not_hold_is_downloaded(tmp_path, served):
    reuse = tmp_path / "release"
    reuse.mkdir()
    (reuse / prepare.NEARBY_KEY).write_bytes(served["bodies"][prepare.NEARBY_KEY])
    (reuse / prepare.AT_KEY).write_bytes(b"an older release's bytes")

    assert prepare.main(["--env", "ua", "--out-dir", str(tmp_path / "out"), "--reuse-dir", str(reuse)]) == 0
    assert served["downloads"] == [f"{RELEASE_URL}/trails.geojson"]


def test_a_download_whose_hash_is_not_the_listed_one_prepares_nothing_and_keeps_the_last_release(tmp_path, served):
    out = tmp_path / "out"
    prepare.main(["--env", "ua", "--out-dir", str(out)])
    served["latest"] = _latest("2026-10-11", {prepare.NEARBY_KEY: "0" * 64, prepare.AT_KEY: served["sha256s"][prepare.AT_KEY]})

    with pytest.raises(SystemExit, match="lists 0000"):
        prepare.main(["--env", "ua", "--out-dir", str(out)])
    assert prepare.prepared(out)["release"] == "2026-10-10-2"


def test_an_environment_with_no_release_has_nothing_to_prepare(tmp_path, served, capsys):
    served["latest"] = {"version": "v", "artifacts": {"conditions/closures.json": {"sha256": "x"}}}

    assert prepare.main(["--env", "ua", "--out-dir", str(tmp_path / "out")]) == 0
    assert "names no release" in capsys.readouterr().out
    assert served["downloads"] == [] and not (tmp_path / "out").exists()


def test_a_release_without_the_ats_own_lines_has_nothing_to_prepare(tmp_path, served, capsys):
    """Prepared without trails.geojson, the cut would leave the A.T. open where a club's area closes it."""
    served["latest"] = _latest("2026-10-10-2", {prepare.NEARBY_KEY: served["sha256s"][prepare.NEARBY_KEY]})

    assert prepare.main(["--env", "ua", "--out-dir", str(tmp_path / "out")]) == 0
    assert "names no release carrying nearby_trails.geojson and trails.geojson" in capsys.readouterr().out
    assert served["downloads"] == []


def test_the_release_output_names_the_current_release_and_prepares_nothing(tmp_path, served):
    output = tmp_path / "github_output"

    assert prepare.main(["--env", "ua", "--release-output", str(output)]) == 0
    assert output.read_text() == "release=2026-10-10-2\n"
    assert served["downloads"] == []

    served["latest"] = {"version": "v", "artifacts": {}}
    prepare.main(["--env", "ua", "--release-output", str(output)])
    assert output.read_text().splitlines()[-1] == "release="


def test_a_release_that_is_not_a_release_id_is_refused_before_it_reaches_a_cache_key(tmp_path, served):
    served["latest"] = _latest("2026-10-10\nrelease=injected", served["sha256s"])

    with pytest.raises(SystemExit, match="not a release id"):
        prepare.main(["--env", "ua", "--release-output", str(tmp_path / "github_output")])
    assert not (tmp_path / "github_output").exists()


def test_local_files_are_prepared_with_no_request(tmp_path, served):
    nearby = _write(tmp_path / "nearby.geojson", [_feature("a", LINE_A)])
    at = _write(tmp_path / "at.geojson", [_feature("centerline:chain:0", AT_LINE)])
    out = tmp_path / "out"

    assert prepare.main(["--from-file", str(nearby), "--at-file", str(at), "--release", "local", "--out-dir", str(out)]) == 0

    assert served["downloads"] == []
    assert {row[1]: row[7] for row in _rows(out)} == {"a": prepare.NEARBY_KEY, "centerline:chain:0": prepare.AT_KEY}


def test_the_at_file_is_refused_without_the_nearby_file(tmp_path):
    with pytest.raises(SystemExit):
        prepare.main(["--at-file", str(tmp_path / "at.geojson"), "--release", "local"])
