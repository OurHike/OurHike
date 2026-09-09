"""export_suggested_hikes.py - the reviewed rows as the artifact the shelf reads (#1290).

The synthetic graph from test_lib_trail_graph_route.py, a one-hike cache in
the shape fetch_nynjtc_hikes.py writes, reference rows, and a registry in a
temp directory - never the real network, cache or rows (TESTING.md).

What is pinned is the three gates and the contract: nothing ships from an
entry that does not reach hikers, nothing ships from a row nobody signed
off, a signed-off row the ground moved from under is dropped loudly and
named in the manifest, and what does ship is spelled the way
lib/suggestedHikesData.ts reads it - ends as snapped coordinates, a loop
closed by repeating its first end, a climb that is absent rather than zero
when nothing priced it, a photo that is absent rather than uncredited.
"""

from __future__ import annotations

import json

import pytest

import export_suggested_hikes as exporter
import route_nynjtc_hikes as script
from lib.nynjtc_hikes import SOURCE_KEY
from tests.test_lib_trail_graph_route import LAT, LON, STEP, graph_files

STEWARD = "New York-New Jersey Trail Conference"


def registry(reaches: bool = True) -> dict:
    return {"sources": [{"key": SOURCE_KEY, "kind": "published_hikes", "steward": STEWARD, "reaches_hikers": reaches}]}


def hike(**overrides) -> dict:
    base = {
        "name": "Pine Meadow Loop",
        "source_url": "https://www.nynjtc.org/hike/pine/",
        "difficulty": "easy-moderate",
        "stated_miles": 0.25,
        "terms": {
            "route-type": [{"slug": "loop", "name": "Loop"}],
            "park": [{"slug": "h", "name": "Harriman State Park"}],
            "trail": [{"slug": "p", "name": "Pine Meadow Trail"}, {"slug": "r", "name": "Ridge Loop"}],
        },
        "overview": ["A short loop."],
        "description": ["Turn right onto the Ridge Loop."],
        "publication": {"submitted_by": "Daniel Chazin", "submitted_on": "2016-08-24", "verified_on": "2021-08-15"},
        "start": {"lat": LAT, "lon": LON, "basis": "marker"},
        "photo": {"key": "photos/" + "a" * 64 + ".jpg", "digest": "a" * 64, "credit": "Daniel Chazin"},
    }
    base.update(overrides)
    return base


def row(**overrides) -> dict:
    base = {
        "status": "reviewed",
        "closed": True,
        "ends": [[LON + 0.2 * STEP, LAT], [LON + 2 * STEP, LAT + 0.9 * STEP]],
        "measured_miles": 0.3,
        "basis": "two junctions",
        "hiker_note": "Starts at the kiosk.",
        "proposed": "2026-09-09",
        "reviewed": "2026-09-10",
    }
    base.update(overrides)
    return base


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    graph_files(processed)
    raw = tmp_path / "raw"
    raw.mkdir()
    cache_path = raw / "nynjtc_hikes.json"
    cache_path.write_text(json.dumps({"hikes": {"hike-pine": hike()}}))
    reference_path = tmp_path / "routes.json"
    reference_path.write_text(json.dumps({"routes": {"hike-pine": row()}}))
    registry_path = tmp_path / "sources.json"
    registry_path.write_text(json.dumps(registry()))
    monkeypatch.setattr(script, "CACHE_PATH", cache_path)
    monkeypatch.setattr(script, "REFERENCE_PATH", reference_path)
    monkeypatch.setattr(exporter, "SOURCES_PATH", registry_path)
    monkeypatch.setattr(exporter, "PROCESSED_DIR", processed)
    monkeypatch.setattr(exporter, "OUT_PATH", processed / "suggested_hikes.json")
    monkeypatch.setattr(exporter, "MANIFEST_PATH", processed / "suggested_hikes_manifest.json")
    return {"processed": processed, "cache": cache_path, "reference": reference_path, "registry": registry_path}


def published(sandbox) -> dict:
    return json.loads((sandbox["processed"] / "suggested_hikes.json").read_text())


class TestTheGates:
    def test_an_entry_that_does_not_reach_hikers_publishes_nothing(self, sandbox, capsys):
        sandbox["registry"].write_text(json.dumps(registry(reaches=False)))

        assert exporter.main() is None
        assert not (sandbox["processed"] / "suggested_hikes.json").exists()
        assert "reaches_hikers: false" in capsys.readouterr().out

    def test_a_proposed_row_is_not_close_enough(self, sandbox, capsys):
        sandbox["reference"].write_text(json.dumps({"routes": {"hike-pine": row(status="proposed", reviewed=None)}}))

        assert exporter.main() is None
        assert not (sandbox["processed"] / "suggested_hikes.json").exists()
        assert "1 proposed, waiting for sign-off" in capsys.readouterr().out

    def test_a_held_row_never_ships(self, sandbox):
        sandbox["reference"].write_text(
            json.dumps(
                {
                    "routes": {
                        "hike-pine": row(),
                        "hike-far": {"status": "held", "reason": "no lines - #1293", "proposed": "2026-09-09"},
                    }
                }
            )
        )

        manifest = exporter.main()
        assert manifest["count"] == 1
        assert [h["id"] for h in published(sandbox)["hikes"]] == [f"{SOURCE_KEY}:hike-pine"]

    def test_a_reviewed_row_the_ground_moved_from_under_is_dropped_loudly(self, sandbox, capsys):
        sandbox["reference"].write_text(
            json.dumps({"routes": {"hike-pine": row(ends=[[LON + 0.2 * STEP, LAT], [LON + 2 * STEP, LAT - 3 * STEP]])}})
        )

        manifest = exporter.main()

        assert manifest["count"] == 0
        assert manifest["dropped"] == ["hike-pine"]
        assert "did not publish" in capsys.readouterr().err
        assert published(sandbox)["hikes"] == []

    def test_a_reviewed_row_with_no_cached_hike_is_dropped_and_named(self, sandbox, capsys):
        sandbox["cache"].write_text(json.dumps({"hikes": {"hike-other": hike()}}))

        manifest = exporter.main()

        assert manifest["dropped"] == ["hike-pine"]
        assert "not in the fetch cache" in capsys.readouterr().err

    def test_reviewed_rows_and_no_cache_is_an_exit(self, sandbox):
        sandbox["cache"].unlink()

        with pytest.raises(SystemExit, match="no fetch cache"):
            exporter.main()


class TestTheContract:
    def test_a_reviewed_hike_ships_what_the_client_validates(self, sandbox):
        manifest = exporter.main()
        record = published(sandbox)["hikes"][0]

        assert record["id"] == f"{SOURCE_KEY}:hike-pine"
        assert record["name"] == "Pine Meadow Loop"
        assert record["miles"] > 0
        assert record["difficulty"] == "easy-moderate"
        assert record["author"] == {"kind": "club", "name": STEWARD}
        assert record["photo"] == {
            "url": "photos/" + "a" * 64 + ".jpg",
            "credit": "Photo by Daniel Chazin",
            "licence": exporter.PHOTO_LICENCE,
        }
        assert manifest["count"] == 1
        assert manifest["with_photo"] == 1
        assert manifest["path"].endswith("suggested_hikes.json")

    def test_the_ends_are_snapped_onto_the_line_and_a_loop_repeats_its_first_end(self, sandbox):
        exporter.main()
        (segment,) = published(sandbox)["hikes"][0]["segments"]

        assert len(segment) == 3
        assert segment[0] == segment[-1]
        assert all(point["poiId"] is None for point in segment)
        # The second end was placed 0.9 * STEP north of the line; what ships
        # is the point on the line, not the point somebody typed.
        assert abs(segment[1]["coord"][1] - (LAT + 0.9 * STEP)) < 1e-9 or abs(segment[1]["coord"][1] - LAT) < 1e-6

    def test_an_open_walk_does_not_close(self, sandbox):
        sandbox["reference"].write_text(json.dumps({"routes": {"hike-pine": row(closed=False)}}))

        exporter.main()
        (segment,) = published(sandbox)["hikes"][0]["segments"]

        assert len(segment) == 2
        assert published(sandbox)["hikes"][0]["closed"] is False

    def test_climb_ships_when_priced_and_is_absent_when_not(self, sandbox):
        exporter.main()
        assert "climb" in published(sandbox)["hikes"][0]
        assert set(published(sandbox)["hikes"][0]["climb"]) == {"gainFt", "lossFt"}

        graph_files(sandbox["processed"], misaligned=True)
        manifest = exporter.main()

        assert "climb" not in published(sandbox)["hikes"][0]
        assert manifest["with_climb"] == 0

    def test_a_photo_with_no_credit_or_no_bytes_does_not_ship(self, sandbox):
        sandbox["cache"].write_text(
            json.dumps({"hikes": {"hike-pine": hike(photo={"key": "photos/" + "b" * 64 + ".jpg", "credit": None})}})
        )
        exporter.main()
        assert "photo" not in published(sandbox)["hikes"][0]

        sandbox["cache"].write_text(
            json.dumps({"hikes": {"hike-pine": hike(photo={"credit": "Jane Daniels", "source_url": "https://x/y.jpg"})}})
        )
        exporter.main()
        assert "photo" not in published(sandbox)["hikes"][0]

    def test_the_detail_fields_carry_nynjtcs_own_facts_beside_this_builds_measurement(self, sandbox):
        exporter.main()
        record = published(sandbox)["hikes"][0]

        assert record["publishedMiles"] == 0.25
        assert record["measured"]["miles"] == record["miles"]
        assert record["measured"]["note"] == exporter.router.SAME_TREAD_NOTE
        assert [leg["name"] for leg in record["measured"]["legs"]]
        assert record["park"] == "Harriman State Park"
        assert record["trails"] == ["Pine Meadow Trail", "Ridge Loop"]
        assert record["publication"]["verifiedOn"] == "2021-08-15"
        assert record["hikerNote"] == "Starts at the kiosk."
        assert record["reviewed"] == "2026-09-10"
        assert record["url"] == "https://www.nynjtc.org/hike/pine/"
        assert record["overview"] == ["A short loop."]

    def test_the_document_is_dated_and_named(self, sandbox):
        exporter.main()
        document = published(sandbox)

        assert document["source"] == SOURCE_KEY
        assert document["generated_at"].endswith("Z")
