"""The registered organizations, and the stable ids the console writes (#929).

Why this exists
---------------
Every join in this pipeline currently rests on one hand-written string
matching another one byte-for-byte. `export_sources.py` groups sources by
`provider`; `_block` matches a licence block's `author` against an entry's
`steward`; `lib/source_registry.py`'s `poi_source_steward` falls back from one
to the other because twelve ATC entries carry a `provider` and no `steward`.

That has already failed silently. `usdm_licence`'s `author` read "National
Drought Mitigation Center, USDA, NOAA and NASA" while its source's `steward`
read "National Drought Mitigation Center, University of Nebraska-Lincoln", so
the U.S. Drought Monitor's recorded terms never reached the sources screen
while every test passed - see that block's `author_note`.

A display string that has changed shape twice in this file's history is the
wrong thing to join on. `steward_id` is the thing that cannot be reworded, and
these tests are what make it a fact rather than a convention: the id set and
the provider set have to agree in both directions, so a registration cannot
introduce an organization by accident and an organization cannot outlive its
last source unnoticed.

IDS ARE PERMANENT. Renaming one is a data migration, not an edit - a phone
holding an older release joins on the id it was built with.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "sources.json").read_text())
ORGS = REGISTRY["organizations"]["orgs"]


def providers() -> set[str]:
    return {source["provider"] for source in REGISTRY["sources"]}


def test_every_provider_has_exactly_one_organization():
    by_provider: dict[str, list[str]] = {}
    for steward_id, org in ORGS.items():
        by_provider.setdefault(org["provider"], []).append(steward_id)

    missing = providers() - set(by_provider)
    assert missing == set(), f"these providers publish data this build ships and have no stable id: {sorted(missing)}"

    doubled = {p: ids for p, ids in by_provider.items() if len(ids) > 1}
    assert doubled == {}, f"one provider, two ids - a join that resolves twice: {doubled}"


def test_no_organization_outlives_its_last_source():
    """The reverse, and the likelier drift: a source removed or a provider
    renamed, leaving a record that reads as current and joins nothing."""
    orphaned = {steward_id: org["provider"] for steward_id, org in ORGS.items() if org["provider"] not in providers()}

    assert orphaned == {}, f"organizations with no registered source: {orphaned}"


@pytest.mark.parametrize("steward_id", sorted(ORGS))
def test_an_id_is_an_id_and_not_a_name(steward_id: str):
    """`org:nynjtc`, never an address and never a display string.

    SOURCE_REGISTRY.md's reason for the shape is worth keeping in front of
    whoever adds the next one: "no contact details in git history, and a
    corrected address takes effect on the next send rather than waiting for a
    data release."
    """
    assert re.fullmatch(r"org:[a-z0-9]+", steward_id), (
        f"{steward_id!r} is not a stable id - lowercase, no spaces, no punctuation "
        "beyond the one colon, and nothing that looks like an address"
    )


@pytest.mark.parametrize("steward_id", sorted(ORGS))
def test_every_organization_says_who_it_is_and_why_it_is_here(steward_id: str):
    org = ORGS[steward_id]

    assert org.get("provider", "").strip(), f"{steward_id}: no provider to join on"
    assert org.get("name", "").strip(), f"{steward_id}: no name a hiker could read"
    # A note that is one line is fine; a note that is absent means the next
    # person reading this list learns nothing the id did not already say.
    assert len(org.get("note", "")) > 40, f"{steward_id}: an organization recorded with no account of itself"


def test_the_drought_monitors_two_names_are_both_deliberate():
    """The one organization whose `provider` and `name` genuinely differ, and
    the reason is worth pinning so nobody 'fixes' it.

    The `provider` string names all four co-producing agencies because the
    DATASET is jointly produced; the `name` names the one organization that
    publishes it, which is also the `steward` string `usdm_licence` joins on.
    Collapsing them would either drop three agencies from a required credit or
    break the licence join for the second time.
    """
    ndmc = ORGS["org:ndmc"]

    assert "USDA" in ndmc["provider"]
    assert ndmc["name"] == "National Drought Mitigation Center, University of Nebraska-Lincoln"
    assert ndmc["name"] == REGISTRY["usdm_licence"]["author"]


def test_every_source_records_what_its_licence_rests_on():
    """`licence_basis`, and the three words are not interchangeable.

    A field rather than prose for the same reason `reaches_hikers` is one: the
    facts were already written down, in the per-source `licence` sentences and
    the `<x>_licence` blocks, and anything wanting to COUNT them had to decide
    by reading those sentences - "which would print a licence claim for data
    nobody publishes the first time one was reworded".
    """
    vocabulary = {"stated_by_org", "maintainer_authorisation", "unresolved"}
    unclassified = [s["key"] for s in REGISTRY["sources"] if s.get("licence_basis") not in vocabulary]

    assert unclassified == [], (
        f"sources with no recorded licence basis: {unclassified}. One of {sorted(vocabulary)} - see licence_basis_comment."
    )


def test_most_of_this_registry_ships_on_the_maintainers_own_word():
    """Re-measured 2026-09-02, and stated as a fact rather than left to be counted.

    29 of the 36 registered sources ship on `maintainer_authorisation` - which
    is NOT a grant from the organization - against 6 where the organization
    stated terms of its own. That includes all thirteen ATC layers, whose
    `atc_licence` basis reads "Maintainer authorisation, on the basis of
    Appalachian Trail Conservancy affiliation".

    The number is here because it is easy to believe the exposure is a handful
    of edge registrations. It is not: it is almost everything, including the
    trail this app was built for. #98 is the open question underneath it.

    WHAT MOVED ON 2026-09-02, and WHY IT IS THE UNCOMFORTABLE DIRECTION. The
    White Mountains arrived (#1207): two USFS layers and NH GRANIT's trails,
    registered `unresolved` in the morning because neither organization states
    any reuse terms, then authorised by the maintainer the same day ("yes do
    publish these. Its publically available info."). So `unresolved` went
    1 -> 4 -> 1 and this count went 26 -> 29.

    It is recorded as the maintainer's authorisation and NOT as `stated_by_org`
    on purpose. "Publicly available" is not itself a reuse grant - that is
    SOURCE_SURVEY.md's rule, and the same rule under which DEC, NYNJTC and
    Mohonk, all equally public, sit in this column rather than the next one.
    Three more sources on the maintainer's own word is exactly the exposure the
    paragraph above says is easy to underestimate, so it grew rather than
    shrank, and that is the honest entry.

    ONE UPGRADE IS AVAILABLE AND UNCLAIMED: `licence_basis_comment` lists "a
    federal public-domain work" as an instance of `stated_by_org`, and the USFS
    layers plausibly are one (17 U.S.C. 105). Claiming it would move 2 from this
    column to that one. See `usfs_licence` for why nobody has.

    This test is expected to change when an organization answers. It should
    change by somebody editing it deliberately, with the org's answer in hand.
    """
    counts: dict[str, int] = {}
    for source in REGISTRY["sources"]:
        counts[source["licence_basis"]] = counts.get(source["licence_basis"], 0) + 1

    assert counts == {"maintainer_authorisation": 29, "stated_by_org": 6, "unresolved": 1}
