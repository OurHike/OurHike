"""Tests for review_flagged_photos.py - the human half of the face gate
(#836): the page that shows what the screen held, and the two commands that
record what a person concluded."""

import json

import pytest

import review_flagged_photos
from lib.photo_screen import load_decisions
from lib.photo_store import local_photo_path, photo_digest

JPEG_BYTES = b"\xff\xd8\xff\xe0 pretend group shot"
DIGEST = photo_digest(JPEG_BYTES)


def _outcomes(raw_dir, photo):
    (raw_dir / "poi_images.json").write_text(
        json.dumps({"pois": {"atc_shelters:glob-1": {"status": "found", "checked": "2026-08-20", "photo": photo}}})
    )


def _flagged_photo(digest=DIGEST, faces=2):
    return {
        "url": "https://upload.wikimedia.org/1-640.jpg",
        "page_url": "https://commons.wikimedia.org/wiki/File:Test.jpg",
        "author": "Jane Doe",
        "license": "CC BY-SA 4.0",
        "taken": "2025-06-18",
        "digest": digest,
        "screen": {"faces": faces, "screener": "test", "on": "2026-08-20"},
    }


@pytest.fixture
def review_env(tmp_path, monkeypatch):
    """Point the script's module-level paths at a scratch tree, the same
    monkeypatch shape the fetch tests use."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    monkeypatch.setattr(review_flagged_photos, "RAW_DIR", raw_dir)
    monkeypatch.setattr(review_flagged_photos, "OUT_PATH", tmp_path / "review" / "photo_screen.html")
    decisions_path = tmp_path / "decisions.json"
    monkeypatch.setattr(review_flagged_photos, "DECISIONS_PATH", decisions_path)
    import lib.photo_screen

    monkeypatch.setattr(lib.photo_screen, "DECISIONS_PATH", decisions_path)
    return raw_dir, tmp_path / "review" / "photo_screen.html", decisions_path


def test_the_page_shows_a_held_photo_with_its_bytes_and_both_commands(review_env):
    raw_dir, out_path, _ = review_env
    _outcomes(raw_dir, _flagged_photo())
    cache = local_photo_path(raw_dir, DIGEST)
    cache.parent.mkdir(parents=True)
    cache.write_bytes(JPEG_BYTES)

    review_flagged_photos.run([])

    page = out_path.read_text()
    assert "1 flagged photo(s) awaiting a look" in page
    assert "data:image/jpeg;base64," in page  # embedded, never hotlinked
    assert "upload.wikimedia.org" not in page
    assert f"--clear {DIGEST}" in page
    assert f"--refuse {DIGEST}" in page
    assert "atc_shelters:glob-1" in page


def test_a_held_photo_whose_bytes_are_not_cached_says_so_instead_of_a_broken_image(review_env):
    raw_dir, out_path, _ = review_env
    _outcomes(raw_dir, _flagged_photo())

    review_flagged_photos.run([])

    page = out_path.read_text()
    assert "Bytes not cached locally" in page
    assert "data:image/jpeg" not in page


def test_unflagged_decided_and_digestless_photos_stay_off_the_page(review_env):
    raw_dir, out_path, decisions_path = review_env
    _outcomes(raw_dir, _flagged_photo(faces=0))

    review_flagged_photos.run([])
    assert "0 flagged photo(s)" in out_path.read_text()

    _outcomes(raw_dir, _flagged_photo())
    decisions_path.write_text(json.dumps({"decisions": {DIGEST: {"decision": "cleared", "on": "2026-08-20"}}}))
    review_flagged_photos.run([])
    assert "0 flagged photo(s)" in out_path.read_text()


def test_clear_and_refuse_write_the_ledger(review_env, capsys):
    raw_dir, _, decisions_path = review_env
    _outcomes(raw_dir, _flagged_photo())

    review_flagged_photos.run(["--clear", DIGEST, "--note", "trail sign, not a person"])

    decisions = load_decisions(decisions_path)
    assert decisions[DIGEST]["decision"] == "cleared"
    assert decisions[DIGEST]["note"] == "trail sign, not a person"
    assert "Recorded" in capsys.readouterr().out

    review_flagged_photos.run(["--refuse", DIGEST])
    assert load_decisions(decisions_path)[DIGEST]["decision"] == "refused"


def test_a_decision_for_a_digest_nothing_holds_warns_about_a_paste_slip(review_env, capsys):
    raw_dir, _, decisions_path = review_env
    _outcomes(raw_dir, _flagged_photo())
    stray = "0" * 64

    review_flagged_photos.run(["--clear", stray])

    # Recorded anyway - the ledger outlives any one crawl - but said out loud.
    assert load_decisions(decisions_path)[stray]["decision"] == "cleared"
    assert "paste slip" in capsys.readouterr().out


def test_an_unknown_flag_is_rejected_rather_than_building_the_page(review_env):
    _, out_path, _ = review_env
    with pytest.raises(SystemExit):
        review_flagged_photos.run(["--claer", DIGEST])
    assert not out_path.exists()


def test_a_trailing_argument_that_is_not_a_note_is_rejected(review_env, capsys):
    raw_dir, _, decisions_path = review_env
    with pytest.raises(SystemExit):
        review_flagged_photos.run(["--refuse", DIGEST, "extra"])
    assert not decisions_path.exists()
