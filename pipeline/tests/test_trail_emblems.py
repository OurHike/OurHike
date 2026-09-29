"""Which long trails wear a badge, and the mark nobody has been asked for (#1543).

`pipeline/reference/trail_emblems.json` lists 67 long-distance trails that
should wear a through-route badge, with the blaze their chip takes. It carries
no artwork and no design for artwork, and these tests are what keep it that
way.

WHETHER A MARK MAY SHIP IS NOT THIS FILE'S QUESTION. `sources.json`'s
`org_marks` block records that per organization and `test_org_marks.py`
enforces it; an earlier draft of this file mirrored that vocabulary per trail,
which tracked nothing org_marks did not already track, and it is gone.

What survives here is narrower: this file must not become a place somebody
draws a mark FROM. test_no_trail_carries_a_drawn_emblem exists because the
first draft carried a shape, a ground colour and a letterform per trail.

An earlier draft of this file carried a per-trail shape, ground colour and
letterform. That is the generated shape the sentence above names, and
test_no_trail_carries_a_drawn_emblem is here because the draft existed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EMBLEMS = ROOT / "reference" / "trail_emblems.json"
CATALOGUE = ROOT / "reference" / "trail_orgs.json"
REGISTRY = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def emblems() -> dict:
    return json.loads(EMBLEMS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def trails(emblems) -> list[dict]:
    return emblems["trails"]


def test_no_trail_carries_a_drawn_emblem(trails):
    """The check that would have caught this file's own first draft.

    A shape, a ground colour or a letterform per trail is a design for a mark
    OurHike has no right to draw. org_marks forbids it in words; this is the
    same refusal where somebody would actually reach for it.
    """
    forbidden = {"emblem", "shape", "ground", "figure", "letters", "letterform", "initials"}
    offenders = sorted(f"{t['slug']}.{key}" for t in trails for key in t if key in forbidden)
    assert offenders == [], (
        f"these rows design a mark rather than naming one: {offenders}. A trail with no "
        "granted mark wears the blaze chip map/trailBadges.ts already draws."
    )


def test_no_trail_row_names_an_image_file(trails):
    """Belt and braces on the same rule, from the asset side.

    test_org_marks.py polices the client's own mark directory. Nothing stops a
    reference file naming a path into it, and a filename is how the next person
    learns an asset was expected.
    """
    blob = json.dumps(trails)
    for smell in ("data:image", "base64", ".svg", ".png", ".jpg", ".webp"):
        assert smell not in blob, f"a trail row carries {smell!r}; this file names no artwork"


def test_every_trail_records_a_blaze_even_when_it_has_none(trails):
    """'none' is a fact about a signed trail, not a missing value.

    It is also 30 of the 67 here, so it is the common case rather than an edge
    one - and the chip for a trail with no blaze is a question this file
    records rather than answers.
    """
    missing = sorted(t["slug"] for t in trails if not t.get("blaze"))
    assert missing == [], f"trails with no blaze recorded at all: {missing}"


def test_every_steward_a_trail_names_is_an_organization_in_the_catalogue(trails):
    """An orphaned steward is a badge pointing at nobody.

    It caught a real one: the Long Path's steward is NYNJTC, whose catalogue
    row was slugged `nynjtc-at` as though it were only an A.T. club, when five
    of its layers already ship.
    """
    known = {o["slug"] for o in json.loads(CATALOGUE.read_text(encoding="utf-8"))["orgs"]}
    dangling = sorted(
        f"{t['slug']} -> {t['steward']}" for t in trails if t["steward"] and t["steward"].removeprefix("org:") not in known
    )
    assert dangling == [], f"trails whose steward is in no catalogue row: {dangling}"


def test_the_two_trails_that_already_wear_a_mark_are_both_here(trails):
    """map/trailBadges.ts's BADGE_MARK_BY_SOURCE has exactly two entries.

    The A.T. and the Long Path, both on the maintainer's own authorisation.
    This file is the list that tier grows to, so a list missing its own first
    two members is describing some other product.
    """
    slugs = {t["slug"] for t in trails}
    assert {"at", "long-path"} <= slugs
