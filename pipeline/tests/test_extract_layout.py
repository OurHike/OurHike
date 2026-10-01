"""The extract layout check, on every pull request: pipeline/ELT.md, "The data checks", check 1.

It holds the shape of pipeline/extract/ and nothing about the network: every
club folder is a managing organisation, holds exactly the eleven type files,
and each file is one of the three forms; every claim resolves to a registry
key or a reviewed file, once; every resource is on a lane. It checks a note's
shape and never its age, so the calendar cannot turn an unrelated pull request
red (check 3, note ageing, is the monthly job's).

THE FOLDERS ARE A SUBSET UNTIL THE MIGRATION FINISHES. Stage 2 of #1793 —
Rebuild the data platform as dlt → dbt: seven contracted marts, a monthly
refresh, published docs, and lighter phone downloads — moves clubs over one at
a time, so "every sources.json key is claimed" cannot hold yet. NOT_YET_EXTRACTED
below is the registry keys still on the old fetchers, by name, so the gap is
a list a reviewer can read and every migrated club shortens it. When it is
empty, the full rule holds and the list goes.
"""

import ast
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from extract._contract import (
    CADENCES,
    EXTRACT_DIR,
    NOT_CLUB_TYPES,
    PIPELINE_DIR,
    TYPES,
    NotAvailable,
    all_resources,
    club_folders,
    discover,
    discover_shared,
    folder_for_slug,
    raw_table,
    slug_for_folder,
)
from extract._kinds import ORGS_TABLE, _registry, _trail_orgs
from extract._run import LANES
from lib.socrata import dataset_url

REGISTRY_PATH = PIPELINE_DIR / "sources.json"
TRAIL_ORGS_PATH = PIPELINE_DIR / "reference" / "trail_orgs.json"

# sources.json keys no club folder claims yet: the providers stage 2 has not
# reached. Remove a key when its club's folder lands; the test below fails in
# both directions, so a key cannot be claimed and listed here at once, and a
# new registry row must be claimed or listed.
NOT_YET_EXTRACTED = frozenset(
    {
        # Its state extracts are gigabytes that belong in the private raw bucket, which
        # is the maintainer's to create: #1652 — Download OSM's Geofabrik extracts at
        # most once a month, into a private raw bucket that outlives the 7-day Actions cache.
        "osm_water",
        # A watch, not a fetch: _shared/usgs/'s, not built yet.
        "usgs_3dhp",
        # Waiting on #1804 — fetch_drought.py fetches droughtmonitor.unl.edu/data/, a
        # path the Drought Monitor's robots.txt disallows for every user agent. The
        # extract does not rebuild a fetch robots.txt refuses.
        "usdm_drought",
    }
)

TODAY = date.today()
FILES = discover()
SHARED_FILES = discover_shared()
EVERY_FILE = FILES + SHARED_FILES
BY_CLUB = {folder.name: [f for f in FILES if f.club == folder.name] for folder in club_folders()}


def managing_slugs() -> set[str]:
    return {slug for slug, row in _trail_orgs(TRAIL_ORGS_PATH).items() if row.get("type") not in NOT_CLUB_TYPES}


def test_there_are_club_folders_to_check():
    """A layout test over zero folders passes vacuously; this is the line that says so."""
    assert {"atc", "nysdec"} <= set(BY_CLUB)


def test_every_folder_is_a_managing_organisation_in_trail_orgs():
    unknown = {folder for folder in BY_CLUB if slug_for_folder(folder) not in managing_slugs()}
    assert not unknown, f"club folders with no managing trail_orgs.json row: {sorted(unknown)}"


def test_folder_names_and_slugs_map_both_ways_exactly():
    """`-` is written `_`, which reverses only while no slug holds an underscore (ELT.md: none of 173 does)."""
    slugs = set(_trail_orgs(TRAIL_ORGS_PATH))
    assert not [slug for slug in slugs if "_" in slug]
    for slug in slugs:
        assert slug_for_folder(folder_for_slug(slug)) == slug


@pytest.mark.parametrize("club", sorted(BY_CLUB))
def test_each_folder_holds_exactly_the_eleven_type_files(club):
    entries = sorted(p.name for p in (EXTRACT_DIR / club).iterdir() if p.name != "__pycache__")
    assert entries == sorted(f"{type_}.py" for type_ in TYPES), (
        "a club folder is the eleven TYPES files and nothing else, no __init__.py included, so the count is exact"
    )


@pytest.mark.parametrize("club_file", FILES, ids=lambda f: f"{f.club}/{f.type}")
def test_each_file_takes_exactly_one_form(club_file):
    assert club_file.form != "invalid", (
        f"{club_file.club}/{club_file.type}.py must define exactly one of CLAIMS + RESOURCES, SHARES or NOT_AVAILABLE"
    )
    if club_file.type == "org":
        assert club_file.form == "claims" and len(club_file.resources) == 1, "org.py is one catalogue row, never a note"
    if club_file.form == "claims" and club_file.type != "org":
        assert club_file.claims and club_file.resources, "a claiming file needs both its claims and their resources"


@pytest.mark.parametrize("club_file", [f for f in FILES if f.shares], ids=lambda f: f"{f.club}/{f.type}")
def test_a_shares_file_names_a_sibling_that_has_resources(club_file):
    sibling = next((f for f in BY_CLUB[club_file.club] if f.type == club_file.shares), None)
    assert sibling is not None and sibling.form == "claims", (
        f"{club_file.club}/{club_file.type}.py shares {club_file.shares!r}, which has no resources of its own"
    )
    assert club_file.shares != club_file.type


@pytest.mark.parametrize("club_file", [f for f in FILES if f.note], ids=lambda f: f"{f.club}/{f.type}")
def test_a_note_is_well_formed(club_file):
    assert isinstance(club_file.note, NotAvailable)
    assert club_file.note.problems(TODAY) == []


def test_a_note_in_the_future_is_refused():
    note = NotAvailable(confirmed=date(2999, 1, 1), checked=("x",), where=("https://example.org",))
    assert note.problems(date(2026, 10, 1)) == ["confirmed 2999-01-01 is in the future"]


def test_a_note_without_what_was_checked_or_where_is_refused():
    note = NotAvailable(confirmed=date(2026, 10, 1), checked=(), where=("http://example.org",))
    assert note.problems(date(2026, 10, 1)) == ["checked must list what was looked at", "where must list https URLs"]


def test_every_claim_is_a_registry_key_or_a_reviewed_file_and_is_claimed_once():
    registry = _registry(REGISTRY_PATH)
    claims = Counter(key for f in EVERY_FILE for key in f.claims)
    twice = sorted(key for key, n in claims.items() if n > 1)
    assert not twice, f"claimed by more than one file: {twice}"
    unresolved = sorted(
        key for key in claims if key not in registry and not (key.startswith("reference/") and (PIPELINE_DIR / key).exists())
    )
    assert not unresolved, f"claims that are neither a sources.json key nor a pipeline/reference/ path: {unresolved}"


def test_a_claiming_file_has_a_resource_for_each_claim_and_no_other():
    for club_file in EVERY_FILE:
        if club_file.type == "org" or club_file.form != "claims":
            continue
        if club_file.unregistered:
            assert not club_file.claims, f"{club_file.path}: an unregistered input claims nothing"
            continue
        # A key may feed two resources (NYNJTC's alerts: posts and terms), so the sets must match.
        assert sorted(set(club_file.claims)) == sorted({r.key for r in club_file.resources}), (
            f"{club_file.club}/{club_file.type}.py: CLAIMS and the RESOURCES' keys must match"
        )


def test_every_registry_key_is_claimed_or_still_listed_as_not_yet_extracted():
    registry = set(_registry(REGISTRY_PATH))
    claimed = {key for f in EVERY_FILE for key in f.claims}
    assert not (claimed & NOT_YET_EXTRACTED), (
        f"claimed and still listed as not yet extracted - take these off NOT_YET_EXTRACTED: {sorted(claimed & NOT_YET_EXTRACTED)}"
    )
    missing = sorted(registry - claimed - NOT_YET_EXTRACTED)
    assert not missing, f"sources.json keys no club folder claims: {missing}"
    stale = sorted(NOT_YET_EXTRACTED - registry)
    assert not stale, f"NOT_YET_EXTRACTED names keys sources.json no longer has: {stale}"


def test_every_resource_is_on_a_lane_and_an_override_says_why():
    carried = {cadence for cadences in LANES.values() for cadence in cadences}
    for resource in all_resources(EVERY_FILE):
        assert resource.cadence in CADENCES
        assert resource.cadence in carried, f"{resource.table}: no lane runs {resource.cadence!r} resources yet"
        if resource.cadence_override is not None:
            assert resource.cadence_reason, f"{resource.table}: a cadence override needs cadence_reason"


def test_no_table_is_written_by_two_resources_except_the_shared_org_table():
    tables = Counter(r.table for r in all_resources(EVERY_FILE))
    shared = sorted(table for table, n in tables.items() if n > 1 and table != ORGS_TABLE)
    assert not shared, f"tables two resources write: {shared}"
    lanes_by_table = {}
    for resource in all_resources(EVERY_FILE):
        lanes_by_table.setdefault(resource.table, set()).add(resource.cadence)
    assert all(len(lanes) == 1 for lanes in lanes_by_table.values()), "a table sits on one pipeline"


def test_raw_table_names_keep_the_double_underscore():
    assert raw_table("nysdec", "dec_lean_tos") == "raw_nysdec__dec_lean_tos"
    assert raw_table("atc", "reference/water_distance.json") == "raw_atc__water_distance"
    assert raw_table("atc", "reference/challenges/atc") == "raw_atc__challenges_atc"


def test_a_club_file_never_names_a_url_to_fetch():
    """Builders take keys. A URL in a club file is either a note's `where` or a mistake, so only notes may hold one."""
    for club_file in EVERY_FILE:
        if club_file.note is not None:
            continue
        tree = ast.parse(club_file.path.read_text())
        strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        docstring = ast.get_docstring(tree) or ""
        copies = {url for note in club_file.same_as for url in note.copy}
        urls = [s for s in strings if s != docstring and s not in copies and re.search(r"https?://", s)]
        assert not urls, f"{club_file.club}/{club_file.type}.py holds a URL outside its docstring: {urls}"


@pytest.mark.parametrize("club_file", [f for f in FILES if f.same_as], ids=lambda f: f"{f.club}/{f.type}")
def test_a_same_as_note_is_well_formed_and_its_original_is_claimed(club_file):
    claimed = {key for f in EVERY_FILE for key in f.claims}
    for note in club_file.same_as:
        assert note.problems(TODAY) == []
        assert note.original in claimed, (
            f"{club_file.club}/{club_file.type}.py: SAME_AS original {note.original!r} is not claimed"
        )


def upstream(entry: dict) -> tuple[str, str]:
    """What a resource reads: the dataset's address, and the filter the server applies to it.

    A Socrata dataset is its domain and four-four id, which is what the resource
    fetches (`nyc_public_restrooms`' `url` names a different dataset;
    ORG_COVERAGE_SURVEY.md §3b). The `where` is part of it because two
    server-side filters over one dataset are two slices, not two copies: NYC's
    Centerline is read once for its paths and once for its park drives, and the
    two predicates shared 0 rows (measured 2026-10-01: 6,496 and 124).
    """
    address = dataset_url(entry["domain"], entry["dataset_id"]) if entry.get("dataset_id") else entry["url"].rstrip("/")
    return address, entry.get("where") or ""


def test_no_dataset_is_extracted_twice_and_no_copy_is_also_a_resource():
    """Decision 34: each upstream dataset is landed once, in its steward's folder."""
    registry = _registry(REGISTRY_PATH)
    reads = Counter(
        (*upstream(registry[r.key]), r.part) for r in all_resources(EVERY_FILE) if r.key in registry and "url" in registry[r.key]
    )
    twice = sorted(read for read, n in reads.items() if n > 1)
    assert not twice, f"two resources read the same upstream: {twice}"
    copies = {url.rstrip("/") for f in FILES for note in f.same_as for url in note.copy}
    addresses = {address for address, _, _ in reads}
    assert not (copies & addresses), f"a SAME_AS copy is also extracted: {sorted(copies & addresses)}"


def test_dlt_telemetry_is_off_and_names_keep_their_case_folding_in_the_committed_config():
    import tomllib

    config = tomllib.loads((PIPELINE_DIR / ".dlt" / "config.toml").read_text())
    assert config["runtime"]["dlthub_telemetry"] is False
    assert config["schema"]["naming"] == "sql_ci_v1"
    assert not (PIPELINE_DIR / ".dlt" / "secrets.toml").exists(), "credentials never go in pipeline/.dlt/"


def test_the_dlt_pin_is_the_same_in_the_extract_and_dev_requirements():
    """requirements-extract.in and requirements-dev.in pin dlt separately (the botocore clash); they move together."""

    def pin(path: Path) -> str:
        lines = [line for line in path.read_text().splitlines() if re.match(r"^dlt(\[|==)", line)]
        assert len(lines) == 1, path
        return lines[0].split("==")[1]

    assert pin(PIPELINE_DIR / "requirements-extract.in") == pin(PIPELINE_DIR / "requirements-dev.in")


def _shared_module(relative: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(relative.replace("/", "."), EXTRACT_DIR / "_shared" / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_umbrella_and_route_only_row_has_exactly_one_not_clubs_line():
    """Decision 18: a row with no folder is still accounted for, so a survey never spends a search on it twice."""
    from extract._contract import NotClub

    orgs = _trail_orgs(TRAIL_ORGS_PATH)
    expected = {slug for slug, row in orgs.items() if row.get("type") in ("national_umbrella", "route_only")}
    not_clubs = _shared_module("not_clubs.py").NOT_CLUBS
    assert set(not_clubs) == expected
    for slug, line in not_clubs.items():
        assert isinstance(line, NotClub) and line.type == orgs[slug]["type"]
        assert line.why.strip() and line.confirmed <= TODAY


def test_every_aggregator_has_a_shared_folder_or_waits_on_a_listed_key():
    """osm, outerspatial and avenza live in _shared/; osm's folder comes with osm_water, which is still listed."""
    orgs = _trail_orgs(TRAIL_ORGS_PATH)
    for slug in sorted(slug for slug, row in orgs.items() if row.get("type") == "aggregator"):
        folder = EXTRACT_DIR / "_shared" / folder_for_slug(slug)
        if not folder.is_dir():
            assert slug == "osm" and "osm_water" in NOT_YET_EXTRACTED, f"{slug} has no _shared/ folder"
            continue
        note = _shared_module(f"{folder_for_slug(slug)}/notes.py").NOT_AVAILABLE
        assert note.problems(TODAY) == [] and note.terms, f"{slug}'s note quotes the terms that refuse it"


def test_shared_folders_never_share_a_name_with_a_club_and_each_resource_names_its_type():
    """A _shared/ folder plays the club's part in `raw_<folder>__<key>`, so a shared name equal to a club's could collide."""
    clubs = {folder.name for folder in club_folders()}
    for shared in SHARED_FILES:
        assert shared.club not in clubs, f"_shared/{shared.club}/ has a club folder's name"
        if shared.resources:
            assert shared.type in TYPES, f"_shared/{shared.club}/{shared.path.name} declares no TYPE among {TYPES}"
            assert shared.claims or shared.unregistered, (
                f"_shared/{shared.club}/{shared.path.name} has resources, no CLAIMS, and no UNREGISTERED reason"
            )
