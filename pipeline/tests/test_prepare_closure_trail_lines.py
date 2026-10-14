"""prepare_closure_trail_lines.py reads a release's nearby trail lines once, into the file the hourly cut of area closures reads.

Decision 187 (S6, the maintainer's poll of 2026-10-11): the hourly build crosses out an area closure's trails where they run
inside it, and these are its lines. No test here touches the network: latest.json and the download are stubbed.
"""

import hashlib
import json

import duckdb
import pytest

import prepare_closure_trail_lines as prepare

LINE_A = {"type": "LineString", "coordinates": [[-73.9700004, 41.03], [-73.97, 41.035]]}
LINE_B = {"type": "MultiLineString", "coordinates": [[[-74.2, 41.2], [-74.2, 41.25]], [[-74.21, 41.2], [-74.21, 41.21]]]}
LINE_C = {"type": "LineString", "coordinates": [[-120.0, 45.0], [-120.0, 45.01]]}


def _feature(feature_id, geometry, **properties):
    return {"type": "Feature", "properties": {"id": feature_id, "source": "oprhp_trails", **properties}, "geometry": geometry}


def _write(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def _rows(out_dir):
    with duckdb.connect() as con:
        return con.execute(
            f"select release, line_id, xmin, ymin, xmax, ymax, geometry from read_parquet('{out_dir / prepare.LINES_FILE}')"
        ).fetchall()


def test_each_line_lands_once_with_its_box_at_the_phone_files_five_decimals_ordered_by_place(tmp_path):
    source = _write(
        tmp_path / "nearby_trails.geojson",
        [_feature("b", LINE_B), _feature("a", LINE_A), _feature("c", LINE_C)],
    )

    document = prepare.prepare(
        tmp_path / "nearby_trails.geojson", tmp_path / "out", release="2026-10-10-2", environment="ua", source_sha256="x"
    )

    rows = _rows(tmp_path / "out")
    assert [row[1] for row in rows] == ["c", "b", "a"], "west to east, so neighbouring lines compress together"
    release, line_id, xmin, ymin, xmax, ymax, geometry = rows[2]
    assert (release, line_id) == ("2026-10-10-2", "a")
    assert json.loads(geometry) == {"type": "LineString", "coordinates": [[-73.97, 41.03], [-73.97, 41.035]]}
    assert (xmin, ymin, xmax, ymax) == (-73.97, 41.03, -73.97, 41.035)
    assert json.loads(rows[1][6])["type"] == "MultiLineString"
    assert document == {
        "schema": 1,
        "environment": "ua",
        "release": "2026-10-10-2",
        "source": "nearby_trails.geojson",
        "source_sha256": "x",
        "lines": 3,
        "vertices": 8,
    }
    assert json.loads((tmp_path / "out" / prepare.RELEASE_FILE).read_text()) == document
    assert source.exists()


def test_one_row_per_line_id_whatever_the_release_holds(tmp_path):
    """A shared id is told apart by each line's own geometry, an exact copy is written once, and a line with no id is
    named by its geometry, so stg_derived__closure_trail_lines' key and its source's exactness test cannot fail."""
    _write(
        tmp_path / "nearby_trails.geojson",
        [
            _feature("twin", LINE_A),
            _feature("twin", LINE_C),
            _feature("copy", LINE_B),
            _feature("copy", LINE_B),
            _feature(None, LINE_C),
        ],
    )

    prepare.prepare(tmp_path / "nearby_trails.geojson", tmp_path / "out", release="r", environment=None, source_sha256=None)

    ids = [row[1] for row in _rows(tmp_path / "out")]
    assert len(ids) == len(set(ids)) == 4
    assert "copy" in ids
    assert sorted(line_id.split("#")[0] for line_id in ids if line_id.startswith("twin")) == ["twin", "twin"]
    assert any(line_id.startswith("geometry:") for line_id in ids)


def test_what_is_not_a_line_or_collapses_at_five_decimals_is_left_out(tmp_path):
    _write(
        tmp_path / "nearby_trails.geojson",
        [
            _feature("point", {"type": "Point", "coordinates": [-74.0, 41.0]}),
            _feature("short", {"type": "LineString", "coordinates": [[-74.25, 41.205], [-74.250001, 41.205]]}),
            _feature("kept", LINE_C),
        ],
    )

    document = prepare.prepare(
        tmp_path / "nearby_trails.geojson", tmp_path / "out", release="r", environment=None, source_sha256=None
    )

    assert [row[1] for row in _rows(tmp_path / "out")] == ["kept"]
    assert document["lines"] == 1


class _Response:
    def __init__(self, document):
        self.document = document

    def json(self):
        return self.document


def _latest(release, sha256):
    return {"release": release, "artifacts": {"nearby_trails.geojson": {"sha256": sha256, "size_bytes": 1}}}


@pytest.fixture
def served(tmp_path, monkeypatch):
    """latest.json and nearby_trails.geojson as a bucket would serve them, and every download counted."""
    source = _write(tmp_path / "served.geojson", [_feature("a", LINE_A)])
    state = {"latest": _latest("2026-10-10-2", hashlib.sha256(source.read_bytes()).hexdigest()), "downloads": []}

    def request(url, **_):
        assert url == "https://data.example/environments/ua/latest.json"
        return _Response(state["latest"])

    def download(url, dest, **kwargs):
        assert kwargs["headers"]["User-Agent"].startswith("OurHike")
        state["downloads"].append(url)
        dest.write_bytes(source.read_bytes())
        return dest

    monkeypatch.setattr(prepare, "request_with_retry", request)
    monkeypatch.setattr(prepare, "download_with_retry", download)
    monkeypatch.setenv("DATA_BASE_URL", "https://data.example")
    return state


def test_a_release_is_downloaded_once_and_prepared_once(tmp_path, served):
    out = tmp_path / "out"

    assert prepare.main(["--env", "ua", "--out-dir", str(out)]) == 0
    assert served["downloads"] == ["https://data.example/environments/ua/releases/2026-10-10-2/nearby_trails.geojson"]
    assert prepare.prepared(out)["release"] == "2026-10-10-2"

    assert prepare.main(["--env", "ua", "--out-dir", str(out)]) == 0
    assert len(served["downloads"]) == 1, "a release already prepared is not read again"


def test_the_squares_steps_copy_is_taken_when_it_is_the_releases_bytes(tmp_path, served):
    reuse = tmp_path / "release"
    reuse.mkdir()
    (reuse / "nearby_trails.geojson").write_bytes((tmp_path / "served.geojson").read_bytes())

    assert prepare.main(["--env", "ua", "--out-dir", str(tmp_path / "out"), "--reuse-dir", str(reuse)]) == 0
    assert served["downloads"] == []


def test_a_download_whose_hash_is_not_the_listed_one_prepares_nothing_and_keeps_the_last_release(tmp_path, served):
    out = tmp_path / "out"
    prepare.main(["--env", "ua", "--out-dir", str(out)])
    served["latest"] = _latest("2026-10-11", "0" * 64)

    with pytest.raises(SystemExit, match="lists 0000"):
        prepare.main(["--env", "ua", "--out-dir", str(out)])
    assert prepare.prepared(out)["release"] == "2026-10-10-2"


def test_an_environment_with_no_release_has_nothing_to_prepare(tmp_path, served, capsys):
    served["latest"] = {"version": "v", "artifacts": {"conditions/closures.json": {"sha256": "x"}}}

    assert prepare.main(["--env", "ua", "--out-dir", str(tmp_path / "out")]) == 0
    assert "names no release" in capsys.readouterr().out
    assert served["downloads"] == [] and not (tmp_path / "out").exists()


def test_the_release_output_names_the_current_release_and_prepares_nothing(tmp_path, served):
    output = tmp_path / "github_output"

    assert prepare.main(["--env", "ua", "--release-output", str(output)]) == 0
    assert output.read_text() == "release=2026-10-10-2\n"
    assert served["downloads"] == []

    served["latest"] = {"version": "v", "artifacts": {}}
    prepare.main(["--env", "ua", "--release-output", str(output)])
    assert output.read_text().splitlines()[-1] == "release="


def test_a_release_that_is_not_a_release_id_is_refused_before_it_reaches_a_cache_key(tmp_path, served):
    served["latest"] = _latest("2026-10-10\nrelease=injected", "x")

    with pytest.raises(SystemExit, match="not a release id"):
        prepare.main(["--env", "ua", "--release-output", str(tmp_path / "github_output")])
    assert not (tmp_path / "github_output").exists()
