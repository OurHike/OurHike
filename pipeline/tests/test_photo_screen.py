"""Tests for lib/photo_screen.py - the face check on fetched Commons photos
and the gate that holds flagged ones out of the export (#836).

The real cascade runs against synthetic images for the negative cases (a
flat gray JPEG, undecodable bytes). There is deliberately no
real-cascade positive case here: the Haar detector does not fire on
drawable cartoon faces (tried while building this - a PIL-drawn face
scores 0), and a committed photograph of a person is not a fixture this
repository should carry. The positive wiring is a measured check in the
module docstring (a real 500px Commons portrait scores 1, 2026-08-20);
everything downstream of the count is tested here with explicit screen
records, which is the shape the count travels in anyway.
"""

import io
import json

import pytest
from PIL import Image

from lib import photo_screen
from lib.photo_screen import (
    detect_faces,
    flagged,
    gate_photos,
    load_decisions,
    record_decision,
    screen_bytes,
    unpublishable_digests,
)


def _jpeg(color=128, size=(200, 200)):
    buffer = io.BytesIO()
    Image.new("L", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


def test_a_flat_gray_jpeg_screens_as_zero_faces_not_as_unscreenable():
    assert detect_faces(_jpeg()) == 0


def test_bytes_that_do_not_decode_screen_as_none_rather_than_raising():
    """A corrupt thumbnail must not kill a forty-minute crawl, and must not
    be recorded as screened-and-clear either - None is 'could not screen',
    which the gate counts and ships."""
    assert detect_faces(b"\xff\xd8\xff\xe0 not actually a jpeg") is None


def test_screen_bytes_names_the_detector_and_the_date():
    record = screen_bytes(_jpeg())
    assert record["faces"] == 0
    assert record["screener"] == photo_screen.SCREENER
    assert record["on"]  # today's date; the value matters less than its presence


def test_flagged_is_an_affirmative_finding_only():
    """Unscreened and undecodable both read as not-flagged: holding them
    would unpublish the whole pre-#836 corpus the day the gate shipped."""
    assert flagged({"screen": {"faces": 2}})
    assert not flagged({"screen": {"faces": 0}})
    assert not flagged({"screen": {"faces": None}})
    assert not flagged({})


def test_the_gate_holds_flagged_undecided_photos_and_ships_the_rest():
    photos = {
        "poi-1": [
            {"digest": DIGEST_A, "screen": {"faces": 0}},
            {"digest": DIGEST_B, "screen": {"faces": 2}},
        ],
        "poi-2": [{"digest": DIGEST_C}],  # fetched before the screen existed
    }

    gated, counts = gate_photos(photos, {})

    assert [photo["digest"] for photo in gated["poi-1"]] == [DIGEST_A]
    assert [photo["digest"] for photo in gated["poi-2"]] == [DIGEST_C]
    assert counts == {"shipped": 2, "held": 1, "refused": 0, "unscreened": 1}


def test_a_cleared_photo_ships_and_a_refused_one_stays_out():
    photos = {
        "poi-1": [{"digest": DIGEST_A, "screen": {"faces": 1}}],
        "poi-2": [{"digest": DIGEST_B, "screen": {"faces": 0}}],
    }
    decisions = {
        DIGEST_A: {"decision": "cleared", "on": "2026-08-20"},
        # Refusal outranks a clean screen: a person saw something the
        # cascade did not, and the person wins.
        DIGEST_B: {"decision": "refused", "on": "2026-08-20"},
    }

    gated, counts = gate_photos(photos, decisions)

    assert [photo["digest"] for photo in gated.get("poi-1", [])] == [DIGEST_A]
    assert "poi-2" not in gated  # a POI whose only photo is refused drops out entirely
    assert counts == {"shipped": 1, "held": 0, "refused": 1, "unscreened": 0}


def test_an_undecodable_screen_ships_and_is_counted_as_unscreened():
    photos = {"poi-1": [{"digest": DIGEST_A, "screen": {"faces": None, "screener": "x", "on": "2026-08-20"}}]}

    gated, counts = gate_photos(photos, {})

    assert [photo["digest"] for photo in gated["poi-1"]] == [DIGEST_A]
    assert counts["unscreened"] == 1


def test_unpublishable_digests_names_held_and_refused_bytes(tmp_path):
    """What publish.py subtracts from its upload set: refused always, and
    flagged-without-a-decision - but never unscreened or cleared photos."""
    outcome_path = tmp_path / "poi_images.json"
    outcome_path.write_text(
        json.dumps(
            {
                "pois": {
                    "a": {"status": "found", "photo": {"digest": DIGEST_A, "screen": {"faces": 1}}},
                    "b": {"status": "found", "photo": {"digest": DIGEST_B, "screen": {"faces": 1}}},
                    "c": {"status": "found", "photos": [{"digest": DIGEST_C}]},
                    "d": {"status": "none"},
                }
            }
        )
    )
    decisions = {
        DIGEST_B: {"decision": "cleared", "on": "2026-08-20"},
        DIGEST_C: {"decision": "refused", "on": "2026-08-20"},
    }

    held = unpublishable_digests(outcome_path, decisions)

    assert held == {DIGEST_A, DIGEST_C}


def test_unpublishable_digests_is_empty_when_no_outcome_file_exists(tmp_path):
    assert unpublishable_digests(tmp_path / "missing.json", {}) == set()


def test_decisions_round_trip_through_the_ledger(tmp_path):
    path = tmp_path / "decisions.json"

    record_decision(DIGEST_A, "cleared", note="trailhead sign, not a face", path=path)
    record_decision(DIGEST_B, "refused", path=path)

    decisions = load_decisions(path)
    assert decisions[DIGEST_A]["decision"] == "cleared"
    assert decisions[DIGEST_A]["note"] == "trailhead sign, not a face"
    assert decisions[DIGEST_B]["decision"] == "refused"
    assert "note" not in decisions[DIGEST_B]


def test_a_later_decision_overwrites_an_earlier_one(tmp_path):
    path = tmp_path / "decisions.json"

    record_decision(DIGEST_A, "refused", path=path)
    record_decision(DIGEST_A, "cleared", note="looked again - it is a carved bear", path=path)

    assert load_decisions(path)[DIGEST_A]["decision"] == "cleared"


def test_recording_preserves_the_ledgers_readme(tmp_path):
    """The committed file opens with a _README explaining itself; a write
    that rebuilt the document from the decisions alone would eat it."""
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps({"_README": ["how this file works"], "decisions": {}}))

    record_decision(DIGEST_A, "cleared", path=path)

    document = json.loads(path.read_text())
    assert document["_README"] == ["how this file works"]
    assert DIGEST_A in document["decisions"]


def test_a_missing_ledger_is_an_empty_one(tmp_path):
    assert load_decisions(tmp_path / "never-written.json") == {}


def test_an_unknown_decision_value_in_the_ledger_raises(tmp_path):
    """This file is hand-adjacent; a typo like "clear" silently treated as
    not-cleared would hold a photo somebody explicitly released."""
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps({"decisions": {DIGEST_A: {"decision": "clear", "on": "2026-08-20"}}}))

    with pytest.raises(ValueError, match="clear"):
        load_decisions(path)


def test_a_malformed_digest_is_refused_at_recording_time(tmp_path):
    """A truncated paste recorded as a key would sit in the ledger deciding
    nothing, forever."""
    with pytest.raises(ValueError):
        record_decision("abc123", "cleared", path=tmp_path / "decisions.json")


def test_the_committed_ledger_parses_and_validates():
    """The real reference/photo_screen_decisions.json, so a typo committed
    in review fails here rather than at the next release's export."""
    load_decisions()


def test_recording_an_invalid_decision_raises_before_touching_the_file(tmp_path):
    path = tmp_path / "decisions.json"
    with pytest.raises(ValueError):
        record_decision(DIGEST_A, "approved", path=path)
    assert not path.exists()
