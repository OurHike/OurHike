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

    `public_gis` joined the three on 2026-10-03 with decision 54's first
    registrations: decision 21a's presumption for a GIS layer an organization
    publishes itself, anonymously, on a public endpoint (pipeline/ELT.md, "Who
    may publish", rule 3), which the `publishable_licence_bases` seed already
    admits for GIS kinds. It is not `stated_by_org`, because the organization
    stated nothing, and not `maintainer_authorisation`, because the
    presumption is a rule over every such layer rather than one ruling.
    """
    vocabulary = {"stated_by_org", "maintainer_authorisation", "unresolved", "public_gis"}
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

    NEW YORK CITY IS A FOURTH KIND, and it is the first one where nobody had
    to answer anything (#1432). nyc_parks_trails and nyc_dot_greenways went
    straight in as `stated_by_org`, 10 -> 12, on terms no agency set and no
    maintainer negotiated: NYC Local Law 11 of 2012 opens the city's published
    data by statute, to everyone. That is why the count moved without an ask
    in the way the paragraphs above describe, and it is worth separating from
    the other three because a statutory grant is the only one here that cannot
    rot - an agency cannot withdraw it by editing a portal field, and a club
    inheriting this project does not have to re-confirm it in its own name.
    What it does NOT settle is the attribution rider (`nyc_licence`), which is
    a condition this project has only half built and ships anyway on the
    maintainer's authorisation of 2026-09-15 - recorded there rather than
    here, because it is not what `licence_basis` is answering.

    WHAT MOVED ON 2026-09-17 (#1533), 15 -> 17 on `stated_by_org`, and it is
    the cheapest movement this column has recorded: `nyc_cscl_paths` and
    `nyc_park_drives` are two more City of New York datasets, so NYC Local Law
    11 of 2012 already covers them and nobody was asked anything. That is what
    `nyc_licence` meant by "a grant made BY STATUTE TO EVERYONE rather than a
    permission granted to this project" - the first time that block paid for a
    registration it was not written for.

    THE DISTINCTION THE PARAGRAPH ABOVE FLATTENS, and it belongs here beside
    the OPRHP/USFS one: `nyc_park_drives` ships on the strongest LICENCE basis
    in this file and the weakest FACTUAL one. The statute settles that the data
    may be republished; it says nothing about whether the rows are true, and
    that entry deliberately contradicts its own source - CSCL posts a 20 mph
    speed limit on Central Park's East Dr, which has been closed to cars since
    2018. Drawing it as walkable rests on the maintainer's decision of
    2026-09-17, tagged `@unvalidated` in the entry. `licence_basis` is not the
    column that would ever show that, which is the reason to say so here.

    WHAT MOVED ON 2026-09-28 (#1711), 29 -> 28 on `maintainer_authorisation`,
    and it is the first movement in this column made by REMOVING a source
    rather than by anybody answering. The maintainer took `nh_granit_trails`
    out altogether: GRANIT describes the layer itself as compiled "for
    planning use only", republished it with renamed columns without notice,
    and redrew most of the White Mountains on top of USFS. It was the thinner
    of the two authorisations the paragraphs above describe, and it is gone
    rather than upgraded.

    WHAT MOVED ON 2026-09-30 (#1778), and it is the largest single movement
    this column has had: seventeen organizations registered at once, from the
    #1543 catalogue, taking the file from 46 sources to 63. Thirteen landed in
    `stated_by_org` and four in `maintainer_authorisation`, so 17 -> 30 there
    and 28 -> 32 here.

    THE THIRTEEN ARE NOT ALL ALIKE AND THE COLUMN HIDES IT, which is the same
    flattery the USFS paragraph above records, now at scale. Two are federal -
    NPS and BLM - and sit here on 17 U.S.C. 105, where the statute means the
    agency never had a grant to make. One, PCTA, published CC BY 4.0, which is
    an actual act of consent and the only one in this batch. The other ten are
    STATE OR MUNICIPAL publications resting on the maintainer's assume-open
    decision of 2026-09-17: section 105 does not reach a state, and what the
    row records is that nothing restricting use was FOUND. That is the weakest
    of the three readings and it is counted beside the strongest.

    The four in this column state nothing at all - NCTA, Alaska Trails, TRTA
    and CDTC - and TRTA is worth naming because its row disagrees with the
    catalogue: the catalogue says "free with registration" and the layer
    answered an anonymous probe, and the row keeps the weaker reading of the
    two rather than the one the probe made convenient.

    NONE OF THE SEVENTEEN REACHES A HIKER. They are all `reaches_hikers:
    false`, so this count now includes a block of registrations whose licence
    reading has never had to be right in production. That is by design -
    features/ORG_BULK_LOAD.md registers before it ships - and it is the thing
    to remember before reading the ratio as exposure.

    This test is expected to change when an organization answers. It should
    change by somebody editing it deliberately, with the org's answer in hand.

    THE SECOND `unresolved` (2026-10-01) is The Green Tunnel's feed,
    `green_tunnel_podcast`: registered because the maintainer reviewed it as
    ATC-sponsored, with nobody yet asked what of the feed may show, and
    `reaches_hikers: false` until somebody is.

    DECISION 53'S JSON API SOURCES (2026-10-03, phase B) add seven, 32 -> 36
    and 30 -> 33. NPS's alerts and road events and USGS's elevated volcanoes
    are federal works, `stated_by_org` on the nps_trails reading. PA DCNR's
    park advisories, TEHCC's wiki announcements, FoOT's condition sheet and
    FMST's recovery map have no terms anybody read that reach this use, and
    publish on the maintainer's decision 53 (facts and a link), which is
    `maintainer_authorisation`. All seven are `reaches_hikers: false` until
    phase C has a mart read their tables.

    DECISION 54'S ELEVATION ROWS (2026-10-03), all `reaches_hikers: false`:
    ATC's Z centerline, `atc_atx_centerline`, rests on `atc_licence` (+1
    here); NJDEP's county high points, `nj_high_elevation_points`, carry the
    Data Distribution Agreement `njdep_licence` reads (+1 `stated_by_org`);
    and NCTA's, PCTA's and PASDA's four state nothing and are `public_gis`.

    DECISION 54'S PLACES WAVE, FEDERAL (2026-10-03): 19 place layers - NPS,
    BLM, USFS, USFWS and USGS boundaries and gazetteers - each `stated_by_org`
    on 17 U.S.C. 105, the reading usfs_licence records, and each at
    `reaches_hikers: false` until a mart reads it.

    DECISION 54'S PLACES WAVE, STATE AND CITY (2026-10-03): 34 layers, 9
    `stated_by_org` (CC0, CC BY 4.0, NJDEP's Data Distribution Agreement) and
    25 `public_gis` (decision 21(a)), each at `reaches_hikers: false`.

    DECISION 54'S PLACES WAVE, CLUBS (2026-10-03): 30 layers, 28 `public_gis`,
    CDTC's CC BY sections `stated_by_org`, and one `unresolved`: the Buckeye
    Trail Association's map outlines, extracted under decision 39 from a
    `refuse` organization and never published until its permission is
    recorded.

    DECISION 54'S TRAIL-LINE ROWS, FEDERAL (2026-10-03), all `reaches_hikers:
    false`: the Park Service's, BLM's and USFS Region 6's 27. 23 are federal
    works on section 105's reading (`stated_by_org`), and 4 are NPS-hosted
    layers whose own items say a county, a university, an intern or a
    contractor made them (`public_gis`, decision 21a).

    DECISION 54'S TRAIL-LINE ROWS, CLUBS AND AGENCIES (2026-10-03), all
    `reaches_hikers: false`: 71 more. 70 rest on decision 21a's presumption
    (`public_gis`), and USACE Mobile District's trails are a federal work
    (`stated_by_org`).

    DECISION 54'S POINTS OF INTEREST, WATER AND SHELTERS FIRST (2026-10-03),
    all `reaches_hikers: false`: 36 club point layers. 32 that state nothing
    or only a disclaimer are `public_gis`; BLM's recreation sites, NPS's
    points and the Smokies' shelters are federal works, `stated_by_org` as
    blm_trails and nps_trails are; and NJDEP's open-space points carry the
    Data Distribution Agreement, `stated_by_org` as njdep_park_trails is.

    DECISION 54'S POINTS OF INTEREST, THE REST (2026-10-03), all
    `reaches_hikers: false`: 33 more. 19 `public_gis` (PA DCNR's five, TDEC's
    three Tennessee State Parks layers and the Cumberland Trail's three, NC
    DPR's park offices, the Ridge Trail's campsites, SBTS's trailheads, CPW's
    two, UGRC's state park campsites and Black Hills Trails' two), and 14
    `stated_by_org`: USGS's six and USFWS's two as federal works, CT DEEP's
    two under CC0, UGRC's trailheads and highest peaks under CC BY 4.0, and
    MA DCR's two Blue Hills layers, whose licenseInfo grants copying and use.

    DECISION 53'S PAGE AND POST NOTICES, FOLDERS N TO Z AND _shared/ (2026-10-03): 68 rows, all
    `reaches_hikers: false`. 16 `stated_by_org`: 15 USFS forests' alerts pages and NPS's Natchez
    Trace status page, federal works on 17 U.S.C. 105. 1 `unresolved`: TATC's republished
    ridgerunner reports, whose licence is the maintainer's open question. 51
    `maintainer_authorisation`: decision 53's facts and a link, and for the 23 whose terms restrict
    copying but not reading (OTA's 14 section pages, DEC, EBRPD, TPWD's two parks, WTA, mass.gov,
    IN.gov, nc.gov and SBTS's copyright line), decision 55, their terms quoted on each row.

    DECISION 53'S PAGES, FEEDS AND WORDPRESS SOURCES, FOLDERS A TO M (2026-10-03): 113 rows, all
    `reaches_hikers: false`. 87 `maintainer_authorisation`, on decision 53 (facts and a link) or,
    where the terms restrict copying and not reading, decision 55 (ATA, Buckeye, the City of Duluth,
    the Mid State Trail, the New England Trail's footer); BLM's 26 `stated_by_org`, federal works on
    17 U.S.C. 105.

    DECISION 54'S WAVE 3, CONTENT FEEDS AND APIS (section C, 2026-10-04): 34 rows, all
    `reaches_hikers: false`. 11 `stated_by_org`, federal works on 17 U.S.C. 105: six podcast feeds
    (USFS's two, BLM's, USGS's, USFWS's and NPS's Park Postcards) and NPS's five content lists. 23
    `unresolved`: thirteen podcast feeds whose <copyright> reserves rights or states nothing that
    reaches this use, and ten club hike, itinerary and wiki lists, whose terms nobody has read as
    reaching a published list. Each quotes what it found on its row; publication is the maintainer's
    call, in dbt, once a mart reads them.

    DECISION 54'S WAVES 2 AND 3, GIS FILES AND GEOGRAPHIC APIS (2026-10-04): 30 rows, registered at
    `reaches_hikers: false`, one of them (Forest Park's trailheads) flipped once its rules were in dbt.
    26 `public_gis`: the clubs' own KML, KMZ, GPX, GeoJSON and CSV files and Google My Maps, and
    MTSG's map-location route, which state no licence or only a copyright line (decision 21a; OTA's
    and NC High Peaks' restrictive site text quoted on each row, decision 37). 4 `stated_by_org`: 3
    federal works on 17 U.S.C. 105, the Forest Service's Nez Perce NHT My Map and the NPS Data API's
    places and campgrounds, and FMST's trailheads sheet, whose own first line says it "can be used or
    adapted as you like", an act of consent like PCTA's.

    DECISION 54'S WAVES 4 AND 5, POINTS ON CLUB PAGES AND IN CLUB PDFS (section S, 2026-10-04): rows
    registered at `reaches_hikers: false`. `public_gis` for the clubs' own pages and PDFs of points that state
    no licence (decision 21a's presumption, read as mtsg_map_locations' row reads it; int_sources__publication
    refuses it on a page or a PDF, rule 6, for the maintainer); `unresolved` for the ATA's water cache boxes,
    whose terms ask written permission for information published online, which no decision answers for points.

    DECISION 54'S WAVES 4 AND 5, CONTENT PAGES AND PDFS (section K, 2026-10-04): 26 rows, all
    `reaches_hikers: false`: 23 read by extract/_pages_content.py, 2 by extract/_pdf_content.py and
    1 WordPress post types; 26 `unresolved`. A club's hike list, challenge list or episode page
    publishes on no decision yet, so each quotes the terms it found on its row and waits on the
    maintainer, in dbt, once a mart reads it.
    """
    counts: dict[str, int] = {}
    for source in REGISTRY["sources"]:
        counts[source["licence_basis"]] = counts.get(source["licence_basis"], 0) + 1

    # Decision 53's ArcGIS closure and warning layers (2026-10-03) add 76 rows, all reaches_hikers false: 11 `maintainer_authorisation`, 35 `public_gis`, 30 `stated_by_org`.
    # Decision 53's page and post notices, folders n to z and _shared/ (2026-10-03), add 68: 51, 16 and 1 (above).
    # Its pages, feeds and WordPress sources in folders a to m (phase B, 2026-10-03) add 113: 87 and 26 (above).
    # Decision 54's wave 3 content feeds and APIs (section C) add 34: 11 and 23; waves 2 and 3's GIS files and
    # geographic APIs add 30: 26 `public_gis` and 4 `stated_by_org` (above). Waves 4 and 5's points (section S)
    # add 6: 5 `public_gis` and 1 `unresolved`; their content pages and PDFs (section K) add 26, all `unresolved`
    # (above). Section S's second batch adds 3 `public_gis` (BRBTC's sections, the Palmetto Trail's passages and
    # OHTA's trailheads), and its fourth 1 `public_gis` (PATC's Tuscarora access points and camping), recounted
    # from the registry 2026-10-04.
    assert counts == {"maintainer_authorisation": 186, "public_gis": 252, "stated_by_org": 192, "unresolved": 54}
