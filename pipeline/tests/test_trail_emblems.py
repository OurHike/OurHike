"""Which long trails wear a badge, and the mark nobody has been asked for (#1543).

`pipeline/reference/trail_emblems.json` lists 67 long-distance trails that
should wear a through-route badge, with the blaze their chip takes. It carries
no artwork and no design for artwork, and these tests are what keep it that
way.

THE RULE THIS FILE LIVES UNDER IS NOT NEW AND IS NOT THIS BRANCH'S.
`sources.json`'s `org_marks` block states it: "UNTIL A GRANT ARRIVES, THE SLOT
RENDERS EMPTY - never a placeholder mark, never an initial, never a generated
shape." `pipeline/tests/test_org_marks.py` gives it teeth for assets. These
tests give it teeth one step earlier, in the file somebody would draw from.

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


def test_every_mark_state_is_one_of_the_registry_s_own_four_words(trails):
    """Not a fifth vocabulary beside org_marks' four.

    A parallel spelling is how two records start disagreeing about whether
    somebody said yes, which is the disagreement that matters most here.
    """
    declared = set(REGISTRY["org_marks"]["state_vocabulary"])
    assert declared == {"not_asked", "asked", "granted", "refused"}
    unknown = sorted({t["mark_state"] for t in trails} - declared)
    assert unknown == [], f"mark states org_marks does not declare: {unknown}"


def test_no_trail_claims_a_grant_no_organization_has_given(trails):
    """Every org_marks row reads not_asked today, and this file may not disagree.

    The day one reads `granted`, it changes in org_marks first and the asset
    arrives in the same pull request - never here, and never alone.
    """
    granted = sorted(t["slug"] for t in trails if t["mark_state"] != "not_asked")
    assert granted == [], (
        f"these trails claim a mark answer nobody has: {granted}. Every org_marks row is not_asked; asking is what changes that."
    )


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
