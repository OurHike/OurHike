"""step_poi_photos.py: the photo manifests export_poi.py attaches, into derived.poi_photos (PO24, PO38).

The gate and the attachment are SQL's and test_dbt_points_of_interest_parity.py
holds them to export_poi.py's; these hold the step to the three facts it
takes from Python's own homes: which records are found photos
(export_poi.load_photo_records()), which Commons photos the face screen
flagged (lib/photo_screen.flagged()), and each digest's decision, read through
load_decisions(), which refuses a value it does not know. No bytes are read,
because none are needed (TESTING.md: no request made).
"""

import json

import duckdb
import pytest

import make_dbt_fixtures
import step_poi_photos
from lib import photo_screen

DIGEST = "a" * 64


def _write(path, pois):
    path.write_text(json.dumps({"pois": pois}))
    return path


def _rows(warehouse):
    with duckdb.connect(str(warehouse), read_only=True) as con:
        return con.execute(
            "select source, poi_id, photo_index, digest, page_url, author, license, taken, screened, flagged, decision "
            "from derived.poi_photos order by source, poi_id, photo_index"
        ).fetchall()


def test_both_shapes_land_as_one_row_per_found_photo(tmp_path):
    commons = _write(
        tmp_path / "commons.json",
        {
            "atc_shelters:a": {"status": "found", "photo": {"digest": DIGEST, "page_url": "p", "screen": {"faces": 2}}},
            "atc_shelters:b": {"status": "none", "checked": "2026-09-01"},
        },
    )
    atc = _write(
        tmp_path / "atc.json",
        {"atc_shelters:c": {"status": "found", "photos": [{"digest": DIGEST, "author": "ATC"}, {"page_url": "q"}]}},
    )
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps({"decisions": {DIGEST: {"decision": "cleared"}}}))
    argv = [
        "--warehouse",
        str(tmp_path / "w.duckdb"),
        "--commons",
        str(commons),
        "--atc",
        str(atc),
        "--decisions",
        str(decisions),
    ]
    assert step_poi_photos.main(argv) == 0
    assert _rows(tmp_path / "w.duckdb") == [
        ("atc", "atc_shelters:c", 0, DIGEST, None, "ATC", None, None, False, False, "cleared"),
        ("atc", "atc_shelters:c", 1, None, "q", None, None, None, False, False, None),
        ("commons", "atc_shelters:a", 0, DIGEST, "p", None, None, None, True, True, "cleared"),
    ]


def test_no_outcome_files_is_no_photos_rather_than_a_failure(tmp_path):
    """export_poi.py's load_photo_records(): a fetcher that has not run is a normal state."""
    argv = [
        "--warehouse",
        str(tmp_path / "w.duckdb"),
        "--commons",
        str(tmp_path / "absent-commons.json"),
        "--atc",
        str(tmp_path / "absent-atc.json"),
        "--decisions",
        str(tmp_path / "absent-decisions.json"),
    ]
    assert step_poi_photos.main(argv) == 0
    assert _rows(tmp_path / "w.duckdb") == []


def test_a_decision_the_ledger_does_not_know_stops_the_step(tmp_path):
    """A typo like "clear" read as not cleared would hold a photo somebody released."""
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps({"decisions": {DIGEST: {"decision": "clear"}}}))
    with pytest.raises(ValueError, match="expected 'cleared' or 'refused'"):
        step_poi_photos.main(["--warehouse", str(tmp_path / "w.duckdb"), "--decisions", str(decisions)])


def test_flagged_is_the_screens_own_answer(tmp_path):
    """photo_screen.flagged(): only an affirmative face count flags; unscreened and undecodable do not."""
    photos = {
        "atc_shelters:faces": {"faces": 1},
        "atc_shelters:clear": {"faces": 0},
        "atc_shelters:undecodable": {"faces": None},
    }
    commons = _write(
        tmp_path / "commons.json",
        {
            **{poi: {"status": "found", "photo": {"digest": DIGEST, "screen": screen}} for poi, screen in photos.items()},
            "atc_shelters:unscreened": {"status": "found", "photo": {"digest": DIGEST}},
        },
    )
    rows = step_poi_photos.manifest_rows(commons, tmp_path / "absent.json", {})
    flagged = {row[1]: (row[8], row[9]) for row in rows}
    assert flagged == {
        "atc_shelters:faces": (True, True),
        "atc_shelters:clear": (True, False),
        "atc_shelters:undecodable": (True, False),
        "atc_shelters:unscreened": (False, False),
    }
    for poi, screen in photos.items():
        assert flagged[poi][1] == photo_screen.flagged({"screen": screen}), poi


def test_the_fixture_manifests_are_in_the_fetchers_shapes(tmp_path):
    raw = tmp_path / "raw"
    make_dbt_fixtures.write_fixtures(raw)
    folder = raw / "poi_photos"
    commons = json.loads((folder / "poi_images.json").read_text())["pois"]
    atc = json.loads((folder / "poi_images_atc.json").read_text())["pois"]
    assert all("photos" not in record for record in commons.values()), "fetch_poi_images.py writes one `photo`"
    assert all("photo" not in record for record in atc.values()), "fetch_atc_photos.py writes a `photos` list"
    photo_screen.load_decisions(folder / "photo_screen_decisions.json")
    # Not where export_poi.py reads by default, and not in the fetchers' byte cache.
    assert not (raw / "poi_images.json").exists() and not (raw / "photos").exists()
