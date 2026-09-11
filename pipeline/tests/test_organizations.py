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

    27 of the 36 registered sources ship on `maintainer_authorisation` - which
    is NOT a grant from the organization - against 8 where the organization
    stated terms of its own. That includes all thirteen ATC layers, whose
    `atc_licence` basis reads "Maintainer authorisation, on the basis of
    Appalachian Trail Conservancy affiliation".

    The number is here because it is easy to believe the exposure is a handful
    of edge registrations. It is not: it is almost everything, including the
    trail this app was built for. #98 is the open question underneath it.

    WHAT MOVED ON 2026-09-02, and it moved three times in one day (#1207). The
    White Mountains arrived as two USFS layers and NH GRANIT's trails, all
    registered `unresolved` because neither organization states any reuse
    terms. The maintainer then authorised publication on the grounds that the
    data is publicly available - recorded as `maintainer_authorisation`,
    because public availability is not itself a reuse grant and that is the
    rule under which DEC, NYNJTC and Mohonk, all equally public, sit in this
    column. The maintainer then made the stronger call: the USFS layers are
    works of the U.S. Government and 17 U.S.C. 105 puts them in the PUBLIC
    DOMAIN, so there is no copyright for the Forest Service to grant or
    withhold.

    So the two USFS entries are `stated_by_org` - `licence_basis_comment`
    names "a federal public-domain work" as an instance of it - and the count
    went 26 -> 29 -> 27 on this column, 6 -> 8 on the next. NH GRANIT stays
    here: it is a university-run state clearinghouse aggregating contributed
    town, land-trust and agency layers, so no public-domain-by-statute
    argument reaches it and the body that could answer for a given segment may
    not be GRANIT at all.

    THE ONE PLACE THIS COUNT FLATTERS THE REGISTRY, said because a number that
    only ever improves is a number nobody re-reads: `stated_by_org` now covers
    two things that are not alike. OPRHP published terms somebody read and
    weighed; USFS published nothing, and the statute means it did not have to.
    Both are sound and only the first is an act of consent. `usfs_licence`
    carries that distinction and the limits of section 105 - domestic only,
    employees not contractors, and no claim on the Forest Service shield.

    WHAT MOVED ON 2026-09-08 (#1288), twice in one day. NYNJTC's Long Path
    section guide (`nynjtc_long_path_guide`) was registered `unresolved` in
    the morning, and deliberately so: it is the first NYNJTC surface with
    STATED terms - their site's Terms & Conditions claim copyright over its
    text and maps - so it was a thing to ask about, where the two extracts
    and the alerts had nothing to read. The maintainer read that and
    authorised it the same day ("make reach_hikers:true - I'm assuming my
    relationship with nynjtc is enough"), so it sits in this column with the
    rest of NYNJTC's sources: 27 -> 28 here, and `unresolved` back to 1.
    `nynjtc_guide_licence` carries the words and what they do not cover.

    WHAT MOVED ON 2026-09-09 (#1290): NYNJTC's Favorite Hikes
    (`nynjtc_favorite_hikes`), 28 -> 29 here. The first NYNJTC surface whose
    permission arrived WITH the ask ("we have their permission ... Include
    everything, the description, the photos"; "We can use anything"), and
    the broadest grant any NYNJTC block records - it ships their prose and
    their photographs, where the other three stop at facts and a link. It
    still sits in this column and not the next, because what this
    repository holds is the maintainer's relay of the permission, not
    NYNJTC's own written words; `nynjtc_hikes_licence` says so and says what
    it does not cover.

    WHAT MOVED ON 2026-09-09 (#1293), and it moved this file's other column
    for once: New Jersey's two trail layers (`njdep_park_trails`,
    `nj_statewide_trails`) registered `unresolved`, 1 -> 3. Their terms are
    STATED and were read whole - the NJDEP Data Distribution Agreement,
    quoted verbatim in `njdep_licence` - and they permit reuse, so this is
    neither a refusal nor a silence. What is missing is a decision to
    satisfy two conditions that need building: the metadata redistributed
    alongside the data, and NJDEP's credit/disclaimer sentence verbatim on
    any map. When that decision is taken and recorded they become
    `stated_by_org`, beside OPRHP's.

    WHAT MOVED ON 2026-09-11, and it is the paragraph above coming true:
    New Jersey's two layers went `unresolved` -> `stated_by_org`, 3 -> 1 on
    that column and 8 -> 10 on this file's other one. The maintainer took the
    decision the block was waiting for, and the two conditions were built
    rather than declared satisfied: `attribution` on both entries is now
    NJDEP's required credit/disclaimer sentence byte for byte, and
    export_sources.py publishes the agreement itself (`terms_verbatim`) and
    where it was read (`terms_source`) on the steward record, so it reaches
    the Sources screen with the lines rather than being summarised away.
    njdep_licence's `basis` carries what that does and does not settle -
    "all the metadata provided" is NJDEP's phrase and plausibly reaches
    further than one agreement and one link, and NJDEP has not been asked.

    SO `stated_by_org` NOW COVERS THREE KINDS OF THING, not two, and the
    paragraph above about it flattering the registry gets one more entry:
    a federal public-domain work, terms somebody published and read, and now
    terms somebody published whose conditions this project had to BUILD
    something to meet. The third is the strongest of the three - it is the
    only one where the organization named a condition and the code answers it
    - and it is also the one most able to rot, because the condition is met by
    a screen that somebody could simplify away. tests/test_export_sources.py's
    `TestTermsTravelWithTheData` is what fails if they do.

    This test is expected to change when an organization answers. It should
    change by somebody editing it deliberately, with the org's answer in hand.
    """
    counts: dict[str, int] = {}
    for source in REGISTRY["sources"]:
        counts[source["licence_basis"]] = counts.get(source["licence_basis"], 0) + 1

    assert counts == {"maintainer_authorisation": 29, "stated_by_org": 10, "unresolved": 1}
