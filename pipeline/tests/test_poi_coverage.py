"""Tests for sources.json's `poi_coverage` block - which orgs give us which POI types (#1092).

Why this exists
---------------
The maintainer's ask was two things, and only one of them is a document: *"Search
those sources for the POI types we have... Maybe we need to track each of the POI
types for the org, and whether or not it is provided."* POI_COVERAGE_SURVEY.md is
the search. The tracking is the `poi_coverage` block, and a tracking table nothing
enforces decays into a snapshot of the day somebody wrote it.

The specific decay these guard against, in the order they will actually happen:

1. **A new org is registered and nobody asks the POI question.** This is the
   likeliest one by far - it is what happened to DEC, whose POI layers were
   named in NYC_SOURCE_SURVEY.md §3 on 2026-08-18 and were still unanswered nine
   days later. `test_every_provider_has_a_verdict` makes registering a source
   without a coverage answer a red suite rather than a thing a future survey
   rediscovers.
2. **A ninth POI type is added and eight orgs quietly do not cover it.**
   lib/poi_schema.POI_TYPES already documents three other places keyed to that
   exact tuple; this is the fourth, and it fails naming itself for the same
   reason the other three do (#492).
3. **A verdict softens into a shrug.** "unsuitable" and "absent" are load-bearing
   words - one means we looked and it fails the bar, the other means we looked
   and there is nothing there - and a free-text status field would let a future
   edit write "maybe" or "partial" into a column a reader trusts to be one of
   five things.
4. **A count without a date.** Every measured number in this repository carries
   when it was measured, because a live layer moves: DEC's hiking layer went
   5,277 -> 5,286 in fourteen days. A count with no date is a claim nobody can
   re-check, which CLAUDE.md's evidence standard treats as worse than no claim.

What these tests deliberately do NOT do: check the counts against the live
services. The numbers came from spike_org_poi_coverage.py and re-running it is
how they are re-verified; a test that hit five agencies' ArcGIS servers would be
a suite that fails when a state government has a bad afternoon. `probed_date` is
the honest record that the number was true once, and the survey says so too.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.poi_schema import POI_TYPES

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "sources.json").read_text())
COVERAGE = REGISTRY["poi_coverage"]

# The five words a verdict may be. Spelled here as well as in the block's own
# `status_vocabulary` so that adding a sixth is a deliberate two-file change -
# the vocabulary is the part a reader trusts most and the part cheapest to widen
# by accident.
STATUSES = frozenset({"shipping", "available", "unsuitable", "absent", "unprobed"})

# The statuses that assert the org publishes something. These are the ones that
# owe a count, because "the org has 331 shelters" and "the org has shelters" are
# different claims and only the first one can be checked.
STATUSES_CLAIMING_SUPPLY = frozenset({"available", "unsuitable"})


def org_bodies() -> list[tuple[str, dict]]:
    """Every org that carries a per-type verdict, skipping the not-a-POI-source ones."""
    return [(name, body) for name, body in COVERAGE["orgs"].items() if "not_a_poi_source" not in body]


def test_status_vocabulary_matches_the_statuses_this_file_enforces():
    """The block documents its own vocabulary; that documentation has to be the real one.

    A block whose prose lists five statuses while the data uses a sixth is worse
    than one with no prose at all - the reader who trusts the list is the one
    this whole file exists to protect.
    """
    assert set(COVERAGE["status_vocabulary"]) == STATUSES


def test_every_provider_has_a_verdict():
    """Registering a source obliges an answer about its org's POIs.

    Keyed on `provider` rather than on a hand-kept list of orgs, so a new
    registration cannot slip past by not being added to a second place.
    """
    providers = {source["provider"] for source in REGISTRY["sources"]}
    missing = providers - set(COVERAGE["orgs"])
    assert not missing, (
        f"{sorted(missing)} publish sources this pipeline reads and have no poi_coverage verdict. "
        "Add one - `not_a_poi_source` with a reason is a complete answer for an org that publishes "
        "no point data at all (see the U.S. Drought Monitor's entry)."
    )


def test_no_verdict_for_an_org_that_is_not_a_source():
    """The other direction: a coverage row for an org nobody fetches is a stale claim.

    Not a hypothetical - an org can be de-registered when its licence answer comes
    back no, and the coverage row would otherwise outlive it and read as current.
    """
    providers = {source["provider"] for source in REGISTRY["sources"]}
    orphans = set(COVERAGE["orgs"]) - providers
    assert not orphans, f"{sorted(orphans)} have a poi_coverage verdict and no registered source"


@pytest.mark.parametrize("org,body", org_bodies())
def test_every_poi_type_is_answered(org: str, body: dict):
    """No blanks - the discipline NYC_SOURCE_SURVEY.md §9 applies to licensing, applied here.

    An absent key and a status of "absent" look the same to a reader skimming and
    mean opposite things: one is a finding, the other is a gap in the survey.
    """
    answered = set(body["types"])
    assert answered == set(POI_TYPES), (
        f"{org} answers {sorted(answered)}; POI_TYPES is {sorted(POI_TYPES)}. "
        "Every type needs a verdict, including 'absent' and 'unprobed'."
    )


@pytest.mark.parametrize("org,body", org_bodies())
def test_every_verdict_uses_the_vocabulary_and_says_why(org: str, body: dict):
    for poi_type, cell in body["types"].items():
        assert cell["status"] in STATUSES, f"{org}/{poi_type}: {cell['status']!r} is not one of {sorted(STATUSES)}"
        # A status on its own is an assertion with no evidence behind it, which is
        # the exact shape CLAUDE.md's standard is about. The note is where the
        # evidence goes, so an empty one is a failure rather than a style nit.
        assert cell.get("note", "").strip(), f"{org}/{poi_type}: a verdict with no note is a claim resting on nothing"


@pytest.mark.parametrize("org,body", org_bodies())
def test_a_supply_claim_carries_a_dated_count(org: str, body: dict):
    """A supply claim needs its number and the day that number was true."""
    for poi_type, cell in body["types"].items():
        if cell["status"] not in STATUSES_CLAIMING_SUPPLY:
            continue
        measured = cell.get("measured")
        assert measured, f"{org}/{poi_type} is {cell['status']!r} and carries no count - what is available, and how much?"
        assert isinstance(measured["features"], int) and measured["features"] > 0, (
            f"{org}/{poi_type}: a supply claim of {measured['features']!r} features is not a supply claim"
        )
        assert measured["date"], f"{org}/{poi_type}: a count with no date cannot be re-checked"
        # The org's own public/visitor flag, where the layer has one. Never
        # larger than the total it is a subset of - a transposition here would
        # overstate how much of a layer the org itself stands behind.
        if "org_flags_public" in measured:
            assert 0 <= measured["org_flags_public"] <= measured["features"], (
                f"{org}/{poi_type}: org_flags_public {measured['org_flags_public']} is not a subset of {measured['features']}"
            )


@pytest.mark.parametrize("org,body", org_bodies())
def test_a_named_source_key_is_a_real_registered_source(org: str, body: dict):
    """A cell may point at a registered source; the pointer has to resolve.

    This is the cross-link that made sources.json the right home for the block
    rather than a file of its own - it is only cheap to check because the
    registry and the coverage sit in one document.
    """
    keys = {source["key"] for source in REGISTRY["sources"]}
    cells = list(body["types"].items()) + list(body.get("extra", {}).items())
    for poi_type, cell in cells:
        key = cell.get("source_key")
        if key is None:
            continue
        assert key in keys, f"{org}/{poi_type} names source_key {key!r}, which is not in sources.json"


def test_a_shipping_verdict_means_an_org_whose_data_reaches_hikers():
    """The strongest word here, and the only one a hiker can see.

    reaches_hikers is the registry's own record of what reaches a release
    (reaches_hikers_comment). An org with no shipping source cannot have a
    shipping POI type, and the disagreement would be invisible on either side
    read alone.

    THIS TEST FOUND ONE ON ITS FIRST RUN, which is why the escape hatch below
    is a field rather than a skip. USGS's NHD stream crossings are on a hiker's
    phone and USGS has no registered source that ships: `usgs_3dhp` is a
    deliberate watch on the successor dataset ("Nothing fetches this"), and the
    bulk NHD GeoPackages fetch_trail_water.py actually downloads are in no entry
    at all. That is a real gap in the registry, not a mis-worded verdict, so the
    cell records it in `unregistered_source` and this test demands that record
    instead of accepting silence. An org that ships without registering may say
    so, once, in writing; it may not do it quietly.
    """
    shipping_orgs = {source["provider"] for source in REGISTRY["sources"] if source.get("reaches_hikers")}
    for org, body in org_bodies():
        for poi_type, cell in body["types"].items():
            if cell["status"] != "shipping" or org in shipping_orgs:
                continue
            assert cell.get("unregistered_source", "").strip(), (
                f"{org}/{poi_type} claims to ship, but no source of theirs has reaches_hikers true. Either the verdict is "
                "wrong, or the data ships from something sources.json does not carry - and if it is the second, say so in "
                "`unregistered_source` so export_sources.py's silence about this org is a known gap rather than a surprise."
            )


def test_dec_water_stays_refused_until_dec_publishes_something_new():
    """The one verdict worth pinning in a test rather than trusting to review.

    Measured 2026-08-27: DEC's only plumbed-water asset type is WATER SUPPLY
    SYSTEM, 23 features, ZERO of them flagged PUBLICUSE Y, and the values that
    read like water are fire ponds ('WATERHOLE'), natural gas wells ('WELL') and
    untested springs. This is a water source on a safety path, so the failure
    mode of a future edit that relaxes it is a hiker walking to a gas well.
    Changing this verdict should mean new data from DEC - a new layer, a public
    flag that flips - not a new reading of the same 23 rows, and a test is how
    that intent survives the next person who sees "unsuitable" and reads it as
    "not done yet".
    """
    water = COVERAGE["orgs"]["NYS DEC"]["types"]["water"]
    assert water["status"] == "unsuitable"
    assert water["measured"]["org_flags_public"] == 0
