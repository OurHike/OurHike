"""Every long trail's emblem says whose mark it follows (#1543).

`pipeline/reference/trail_emblems.json` gives 67 long-distance trails an
emblem, and 44 of those emblems follow a mark the trail's steward owns and
nobody has asked them about. That is a real position this project is taking,
and the point of these tests is that the position stays VISIBLE rather than
becoming a thing everyone half-remembers.

features/TRAIL_BLAZE_COLORS.md is why the file exists at all: line width
answers "is this a through-route", and it says outright that a second
through-route turns that question into "which through-route". The 11 new
endpoints in features/ORG_BULK_LOAD.md are that second one arriving.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REFERENCE = Path(__file__).resolve().parents[1] / "reference"
EMBLEMS = REFERENCE / "trail_emblems.json"
CATALOGUE = REFERENCE / "trail_orgs.json"

MARK_STATES = {"org_mark_not_asked", "public_domain", "own_work"}


@pytest.fixture(scope="module")
def emblems() -> dict:
    return json.loads(EMBLEMS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def trails(emblems) -> list[dict]:
    return emblems["trails"]


def test_every_trail_records_whose_mark_its_emblem_follows(trails, emblems):
    """The field that keeps the trademark position greppable.

    `grep org_mark_not_asked` has to answer "which emblems are somebody else's
    mark, used without asking" in one command. A trail with no mark_state, or
    one outside the vocabulary, is an emblem nobody can audit.
    """
    assert set(emblems["_mark_state"]) == MARK_STATES
    unmarked = sorted(t["slug"] for t in trails if t.get("mark_state") not in MARK_STATES)
    assert unmarked == [], f"emblems with no auditable mark state: {unmarked}"


def test_a_mark_we_never_asked_about_is_never_recorded_as_licensed(trails):
    """There is no `licensed` value, because no organization has licensed one.

    export_sources.py publishes mark_state per source and the whole registry
    reads not_asked - test_says_no_organization_has_licensed_a_mark asserts it.
    This file must not become the place that quietly disagrees.
    """
    assert not any(t["mark_state"] == "licensed" for t in trails), (
        "no organization has licensed a mark to OurHike; if one ever does, change "
        "export_sources.py's published mark_state in the same pull request"
    )


def test_every_steward_an_emblem_names_is_an_org_in_the_catalogue(trails):
    """An emblem pointing at an organization that is not in the registry is an orphan.

    It caught a real one: the Long Path's steward is NYNJTC, whose catalogue row
    was slugged `nynjtc-at` as though it were only an A.T. club, when five of
    its layers already ship.
    """
    known = {o["slug"] for o in json.loads(CATALOGUE.read_text(encoding="utf-8"))["orgs"]}
    dangling = sorted(
        f"{t['slug']} -> {t['steward']}" for t in trails if t["steward"] and t["steward"].removeprefix("org:") not in known
    )
    assert dangling == [], f"emblems whose steward is in no catalogue row: {dangling}"


def test_a_trail_with_no_maintainer_uses_our_own_emblem_and_says_so(trails):
    """The 13 route-only trails have no steward, so they can follow no mark.

    Their emblem is OurHike's own and its ground is dotted on purpose - it says
    unmaintained route rather than trail, which is a safety-relevant difference
    and the one thing the emblem must not flatten.
    """
    ownerless = [t for t in trails if t["steward"] is None]
    assert len(ownerless) == 13
    wrong = sorted(t["slug"] for t in ownerless if t["mark_state"] != "own_work" or t["emblem"]["shape"] != "dotted-circle")
    assert wrong == [], f"routes with no maintainer drawn as though they had one: {wrong}"


def test_every_emblem_shape_is_one_the_client_knows_how_to_draw(trails, emblems):
    """The emblem is a specification, not artwork - so the shape vocabulary is closed.

    An unknown shape renders as nothing, and a long trail with no emblem on a
    map carrying several is worse than a map carrying none.
    """
    drawable = set(emblems["_shapes"])
    unknown = sorted({t["emblem"]["shape"] for t in trails} - drawable)
    assert unknown == [], f"shapes nothing can draw: {unknown}"


def test_no_emblem_embeds_an_image(trails):
    """The file describes emblems; it must never carry somebody's logo bytes.

    A committed logo file is a permanent publication of a third party's
    artwork, which is a different and much worse thing than a shape spec - and
    it is the shape of the mistake CLAUDE.md's build-output rule exists to stop.
    """
    blob = json.dumps(trails)
    for smell in ("data:image", "base64", ".svg", ".png"):
        assert smell not in blob, f"an emblem row carries {smell!r} - specs only, never artwork"


def test_a_blaze_colour_is_recorded_for_every_trail_even_when_there_is_none(trails):
    """'none' is a fact about a signed trail, not a gap.

    nh_granit_trails' notes record the same distinction and record getting it
    backwards once: a blank blaze in the White Mountains means unblazed, which
    is true, and rendering it as unknown would be the lie.
    """
    missing = sorted(t["slug"] for t in trails if not t.get("blaze"))
    assert missing == [], f"trails with no blaze recorded at all: {missing}"
