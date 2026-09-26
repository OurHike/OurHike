"""The podcast list's gate (#1683): what a row must be before a phone sees it,
and that the committed list passes it."""

from __future__ import annotations

import json

import pytest

import export_podcasts
from lib.podcasts import MAX_AT_MILE, validate
from lib.r2_keys import validate_key

#: A real-shaped id: 22 base-62 characters. Not a real episode.
GOOD_ID = "0aBcDeFgHiJkLmNoPqRsTu"


def row(**overrides):
    base = {
        "spotify_id": GOOD_ID,
        "title": "An episode",
        "show": "A show",
        "minutes": 48,
        "hikes": ["nynjtc_hike_finder:7909"],
        "reviewed": "2026-09-26",
    }
    base.update(overrides)
    return {key: value for key, value in base.items() if value is not None}


def dropped_reason(candidate) -> str:
    result = validate([candidate])
    assert result.episodes == [], f"expected {candidate!r} to be dropped"
    assert len(result.dropped) == 1
    return result.dropped[0][1]


def test_the_committed_list_publishes_every_row():
    """The reason a typo is a red pull request rather than an episode that
    silently never appears: export_podcasts.py refuses to upload a list that
    dropped anything, and this runs the same gate on every change to it."""
    reference = json.loads(export_podcasts.REFERENCE_PATH.read_text(encoding="utf-8"))
    _, dropped = export_podcasts.build_document(reference)
    assert dropped == [], "\n".join(f"{label}: {why}" for label, why in dropped)


def test_a_complete_row_publishes_without_its_review_fields():
    result = validate([row(note="the park's history", at_miles=[[480, 512.5]])])
    assert result.dropped == []
    document, _ = export_podcasts.build_document({"episodes": [row(note="x", at_miles=[[480, 512.5]])]})
    assert document["episodes"] == [
        {
            "spotify_id": GOOD_ID,
            "title": "An episode",
            "show": "A show",
            "minutes": 48,
            "hikes": ["nynjtc_hike_finder:7909"],
            "at_miles": [[480.0, 512.5]],
        }
    ]


def test_an_unknown_length_is_left_out_rather_than_published_as_zero():
    document, dropped = export_podcasts.build_document({"episodes": [row(minutes=None)]})
    assert dropped == []
    assert "minutes" not in document["episodes"][0]


@pytest.mark.parametrize(
    ("candidate", "reason_fragment"),
    [
        (row(spotify_id="https://open.spotify.com/episode/0aBcDeFgHiJkLmNoPqRsTu"), "22 characters"),
        (row(spotify_id="0aBcDeFgHiJkLmNoPqRsT"), "22 characters"),
        (row(title="  "), "title and show"),
        (row(show=None), "title and show"),
        (row(minutes=0), "minutes"),
        (row(minutes=True), "minutes"),
        (row(minutes=47.5), "minutes"),
        (row(hikes="nynjtc_hike_finder:7909"), "hikes"),
        (row(hikes=[""]), "hikes"),
        (row(at_miles=[[512, 480]]), "run forward"),
        (row(at_miles=[[0, MAX_AT_MILE + 1]]), "run forward"),
        (row(at_miles=[480, 512]), "[start, end]"),
        (row(reviewed=None), "reviewed"),
        (row(reviewed="26/09/2026"), "reviewed"),
        (row(hikes=None), "at least one of hikes or at_miles"),
        (row(at_mile=[[1, 2]]), "unknown field"),
    ],
)
def test_a_row_that_cannot_be_published_is_dropped_with_its_reason(candidate, reason_fragment):
    assert reason_fragment in dropped_reason(candidate)


def test_a_row_anchored_only_to_miles_publishes():
    result = validate([row(hikes=None, at_miles=[[480, 512]])])
    assert result.dropped == []
    assert result.episodes[0].hikes == ()


def test_the_same_episode_twice_keeps_the_first_and_drops_the_second():
    result = validate([row(), row(title="Same id, second row")])
    assert [episode.title for episode in result.episodes] == ["An episode"]
    assert "listed twice" in result.dropped[0][1]


def test_one_bad_row_costs_that_row_and_not_the_list():
    other = row(spotify_id="1aBcDeFgHiJkLmNoPqRsTu")
    result = validate([row(minutes=-1), other])
    assert [episode.spotify_id for episode in result.episodes] == ["1aBcDeFgHiJkLmNoPqRsTu"]
    assert len(result.dropped) == 1


def test_main_writes_the_list(tmp_path, monkeypatch):
    reference = tmp_path / "podcast_episodes.json"
    reference.write_text(json.dumps({"episodes": [row()]}))
    out = tmp_path / "out" / "episodes.json"
    monkeypatch.setattr(export_podcasts, "REFERENCE_PATH", reference)
    monkeypatch.setattr(export_podcasts, "OUT_PATH", out)

    assert export_podcasts.main([]) == 0
    assert json.loads(out.read_text())["episodes"][0]["spotify_id"] == GOOD_ID


def test_main_writes_nothing_when_a_row_was_dropped(tmp_path, monkeypatch, capsys):
    """A list that shrank must not replace the one already on phones."""
    reference = tmp_path / "podcast_episodes.json"
    reference.write_text(json.dumps({"episodes": [row(), row(spotify_id="bad")]}))
    out = tmp_path / "out" / "episodes.json"
    monkeypatch.setattr(export_podcasts, "REFERENCE_PATH", reference)
    monkeypatch.setattr(export_podcasts, "OUT_PATH", out)

    assert export_podcasts.main(["--upload"]) == 1
    assert not out.exists()
    assert "22 characters" in capsys.readouterr().err


def test_the_key_is_legal_in_this_bucket():
    assert validate_key(export_podcasts.PODCASTS_KEY) is None


def test_refuses_to_upload_unless_writing_is_switched_on(tmp_path, monkeypatch):
    monkeypatch.delenv(export_podcasts.WRITE_ENABLED_ENV_VAR, raising=False)
    path = tmp_path / "episodes.json"
    path.write_text("{}")
    with pytest.raises(SystemExit, match="R2_WRITE_ENABLED"):
        export_podcasts.upload(path)


def test_refuses_a_key_the_layout_would_refuse(tmp_path, monkeypatch):
    monkeypatch.setenv(export_podcasts.WRITE_ENABLED_ENV_VAR, "true")
    path = tmp_path / "episodes.json"
    path.write_text("{}")
    with pytest.raises(SystemExit):
        export_podcasts.upload(path, key="podcasts/Episodes_v2.json")
