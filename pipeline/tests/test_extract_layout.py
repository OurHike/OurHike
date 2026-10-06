"""The extract layout check, on every pull request: pipeline/ELT.md, "The data checks", check 1.

It holds the shape of pipeline/extract/ and nothing about the network: every
managing organisation in trail_orgs.json answers each of the ten FILE_TYPES
exactly once, with a resource file in its folder or a row of
extract/not_available.toml (decision 88), and has one catalogue row; a club
folder holds only resource files, and only a managing club has one; every row
is a well-formed note or a share naming a sibling with resources; every claim
resolves to a registry key or a reviewed file, once; every resource is on a
lane. It checks a note's shape and never its age, so the calendar cannot turn
an unrelated pull request red (check 3, note ageing, is the monthly job's).

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
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from extract._contract import (
    CADENCES,
    EXTRACT_DIR,
    FILE_TYPES,
    NOT_AVAILABLE_FILE,
    NOT_CLUB_TYPES,
    PIPELINE_DIR,
    TYPES,
    ClubFile,
    NotAvailable,
    Resource,
    all_resources,
    club_folders,
    discover,
    discover_shared,
    folder_for_slug,
    raw_table,
    read_not_available,
    slug_for_folder,
)
from extract._kinds import ORGS_TABLE, CatalogueRow, ConditionsQuery, NwsAlerts, _registry, _trail_orgs
from extract._run import CONDITIONS_JOB, HOURLY_JOB_TABLES, LANES, LEGS, NOTICES_JOB, job_of, lane_resources, leg_tables
from lib.socrata import dataset_url

REGISTRY_PATH = PIPELINE_DIR / "sources.json"
TRAIL_ORGS_PATH = PIPELINE_DIR / "reference" / "trail_orgs.json"

# sources.json keys no club folder claims yet: the providers stage 2 has not
# reached. Remove a key when its club's folder lands; the test below fails in
# both directions, so a key cannot be claimed and listed here at once, and a
# new registry row must be claimed or listed.
NOT_YET_EXTRACTED = frozenset(
    {
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
NOT_AVAILABLE_PATH = EXTRACT_DIR / NOT_AVAILABLE_FILE
FOLDERS = [folder.name for folder in club_folders()]
BY_CLUB: dict[str, list[ClubFile]] = {}
for _answer in FILES:
    BY_CLUB.setdefault(_answer.club, []).append(_answer)
ROWS = [f for f in FILES if f.is_row]
#: The answers that are files of their own: everything but the rows and the catalogue rows discover() makes.
PY_FILES = [f for f in EVERY_FILE if f.path.suffix == ".py"]


def managing_slugs() -> set[str]:
    return {slug for slug, row in _trail_orgs(TRAIL_ORGS_PATH).items() if row.get("type") not in NOT_CLUB_TYPES}


def managing_clubs() -> set[str]:
    return {folder_for_slug(slug) for slug in managing_slugs()}


def home(answer: ClubFile) -> str:
    """Where an answer is written, as a reader would look for it."""
    if answer.is_row:
        return f"{NOT_AVAILABLE_FILE} [{answer.club}.{answer.type}]"
    if answer.path.suffix == ".py":
        return f"{answer.club}/{answer.path.name}"
    return f"{answer.club}'s catalogue row"


def answer_problems(answers: list[ClubFile], managing: set[str]) -> list[str]:
    """Why the answers are not exactly one per managing club and FILE_TYPES type, or [] when they are (decision 88).

    Each club and type is answered by its resource file or its row of not_available.toml, never both and never
    neither; an answer for a club that is not managing, or for a type outside FILE_TYPES, is a problem too.
    """
    homes: dict[tuple[str, str], list[str]] = {}
    problems = []
    for answer in answers:
        if answer.type == "org" and not answer.is_row:
            continue  # the catalogue rows, which test_every_managing_club_has_exactly_one_catalogue_row holds
        if answer.type not in FILE_TYPES:
            problems.append(f"{home(answer)}: {answer.type!r} is not one of the ten types a club answers {FILE_TYPES}")
            continue
        homes.setdefault((answer.club, answer.type), []).append(home(answer))
    for club in sorted(managing):
        for type_ in FILE_TYPES:
            found = homes.get((club, type_), [])
            if not found:
                problems.append(f"{club} x {type_}: answered by neither {club}/{type_}.py nor a [{club}.{type_}] row")
            elif len(found) > 1:
                problems.append(f"{club} x {type_}: answered {len(found)} times, by {' and by '.join(found)}")
    for (club, type_), found in sorted(homes.items()):
        if club not in managing:
            problems.append(f"{found[0]}: {club!r} is not a managing club in trail_orgs.json")
    return problems


def test_there_are_club_folders_and_rows_to_check():
    """A layout test over zero folders or zero rows passes vacuously; this is the line that says so."""
    assert {"atc", "nysdec"} <= set(FOLDERS)
    assert len(ROWS) > 1000, f"{NOT_AVAILABLE_FILE} gave {len(ROWS)} rows"


def test_every_folder_is_a_managing_organisation_in_trail_orgs():
    unknown = {folder for folder in FOLDERS if slug_for_folder(folder) not in managing_slugs()}
    assert not unknown, f"club folders with no managing trail_orgs.json row: {sorted(unknown)}"


def test_every_managing_club_answers_every_type_exactly_once_by_a_resource_file_or_a_row():
    """Decision 13's guarantee, as decision 88 keeps it: no club leaves a type unanswered, and none answers one twice."""
    problems = answer_problems(FILES, managing_clubs())
    assert not problems, "\n".join(problems)


def test_no_row_names_a_type_its_club_folder_also_has_a_file_for():
    """The case the exactly-once test also catches, named on its own: a row left behind when the resource file landed."""
    files = {(f.club, f.type) for f in FILES if f.path.suffix == ".py"}
    beside = sorted(
        f"{NOT_AVAILABLE_FILE} [{f.club}.{f.type}] beside {f.club}/{f.type}.py" for f in ROWS if (f.club, f.type) in files
    )
    assert not beside, "retire the row when the resource file lands:\n" + "\n".join(beside)


def test_the_rows_are_sorted_by_club_then_type():
    """So a reader finds a row where they expect it, and two sessions adding rows for different clubs edit apart."""
    order = [(row.club, row.type) for row in read_not_available(NOT_AVAILABLE_PATH)]
    assert order == sorted(order), next(f"[{a[0]}.{a[1]}] before [{b[0]}.{b[1]}]" for a, b in zip(order, order[1:]) if a > b)


def test_every_managing_club_has_exactly_one_catalogue_row():
    catalogue = [f for f in FILES if f.type == "org"]
    assert sorted(f.club for f in catalogue) == sorted(managing_clubs())
    for answer in catalogue:
        assert not answer.is_row, f"{home(answer)}: the catalogue row is made from trail_orgs.json, never a row"
        assert [type(r) for r in answer.resources] == [CatalogueRow], home(answer)
        assert (answer.resources[0].club, answer.resources[0].type) == (answer.club, "org")


def test_answers_missing_given_twice_or_for_a_club_that_is_not_managing_are_each_named():
    """answer_problems() itself, on invented answers: the checks above would pass vacuously if it found nothing."""
    note = NotAvailable(confirmed=date(2026, 10, 1), checked=("x",), where=("https://example.org",))
    resource = Resource(key="k", club="club_a", type="closures")
    answers = [
        ClubFile(
            club="club_a", type="closures", path=EXTRACT_DIR / "club_a" / "closures.py", claims=("k",), resources=(resource,)
        ),
        ClubFile(club="club_a", type="closures", path=NOT_AVAILABLE_PATH, note=note),
        ClubFile(club="not_a_club", type="photos", path=NOT_AVAILABLE_PATH, note=note),
        ClubFile(club="club_a", type="trail_line", path=NOT_AVAILABLE_PATH, note=note),
    ]
    answers += [
        ClubFile(club="club_a", type=t, path=NOT_AVAILABLE_PATH, note=note)
        for t in FILE_TYPES
        if t not in ("closures", "warnings")
    ]
    assert answer_problems(answers, {"club_a"}) == [
        f"{NOT_AVAILABLE_FILE} [club_a.trail_line]: 'trail_line' is not one of the ten types a club answers {FILE_TYPES}",
        f"club_a x closures: answered 2 times, by club_a/closures.py and by {NOT_AVAILABLE_FILE} [club_a.closures]",
        "club_a x warnings: answered by neither club_a/warnings.py nor a [club_a.warnings] row",
        f"{NOT_AVAILABLE_FILE} [not_a_club.photos]: 'not_a_club' is not a managing club in trail_orgs.json",
    ]


def test_folder_names_and_slugs_map_both_ways_exactly():
    """`-` is written `_`, which reverses only while no slug holds an underscore (ELT.md: none of 173 does)."""
    slugs = set(_trail_orgs(TRAIL_ORGS_PATH))
    assert not [slug for slug in slugs if "_" in slug]
    for slug in slugs:
        assert slug_for_folder(folder_for_slug(slug)) == slug


@pytest.mark.parametrize("club", FOLDERS)
def test_a_club_folder_holds_only_resource_files_named_for_the_ten_types(club):
    """Decision 88: a folder is its resource files, no __init__.py, no org.py, and no note or share, which are rows."""
    entries = sorted(p.name for p in (EXTRACT_DIR / club).iterdir() if p.name != "__pycache__")
    allowed = {f"{type_}.py" for type_ in FILE_TYPES}
    assert entries and set(entries) <= allowed, (
        f"{club}/ holds {sorted(set(entries) - allowed)}; a folder holds only {sorted(allowed)}"
    )
    for answer in BY_CLUB[club]:
        if answer.path.suffix == ".py":
            assert answer.form in ("claims", "same_as"), (
                f"{home(answer)} is a {answer.form}; a note or a share is a row of {NOT_AVAILABLE_FILE}, never a file"
            )


@pytest.mark.parametrize("club_file", FILES, ids=lambda f: f"{f.club}/{f.type}")
def test_each_answer_takes_exactly_one_form(club_file):
    assert club_file.form != "invalid", (
        f"{home(club_file)} must be exactly one of CLAIMS + RESOURCES, a share or a note (SAME_AS may ride CLAIMS)"
    )
    if club_file.type == "org":
        assert club_file.form == "claims" and len(club_file.resources) == 1, "a catalogue row is one resource, never a note"
    if club_file.form == "claims" and club_file.type != "org":
        assert club_file.claims and club_file.resources, "a claiming file needs both its claims and their resources"
    if club_file.is_row:
        assert club_file.form in ("note", "shares"), f"{home(club_file)} is a {club_file.form}"


@pytest.mark.parametrize("club_file", [f for f in FILES if f.shares], ids=lambda f: f"{f.club}/{f.type}")
def test_a_share_names_a_sibling_type_whose_resource_file_has_resources(club_file):
    sibling = next((f for f in BY_CLUB[club_file.club] if f.type == club_file.shares and not f.is_row), None)
    assert sibling is not None and sibling.form == "claims" and sibling.resources, (
        f"{home(club_file)} shares {club_file.shares!r}, which has no resource file of its own"
    )
    assert club_file.shares != club_file.type


@pytest.mark.parametrize("club_file", [f for f in FILES if f.note], ids=lambda f: f"{f.club}/{f.type}")
def test_a_note_is_well_formed_dated_no_later_than_today_and_names_what_was_checked_and_where(club_file):
    assert club_file.is_row, f"{home(club_file)}: a note is a row of {NOT_AVAILABLE_FILE}"
    assert isinstance(club_file.note, NotAvailable)
    assert club_file.note.problems(TODAY) == []


def _rows(tmp_path, text: str) -> list[ClubFile]:
    path = tmp_path / NOT_AVAILABLE_FILE
    path.write_text(text, encoding="utf-8")
    return read_not_available(path)


def test_a_row_reads_back_as_the_note_or_share_its_file_gave(tmp_path):
    rows = _rows(
        tmp_path,
        """
[club_a.elevation]
confirmed = 2026-10-01
recheck_after_days = 30
summary = "Nothing published."
checked = ["the ArcGIS root"]
where = ["https://example.org/arcgis/rest/services"]
terms = 'the "no automated access" clause'
reason = "refused"

[club_a.warnings]
shares = "closures"
""",
    )
    assert [(row.club, row.type, row.form, row.summary) for row in rows] == [
        ("club_a", "elevation", "note", "Nothing published."),
        ("club_a", "warnings", "shares", None),
    ]
    assert rows[0].note == NotAvailable(
        confirmed=date(2026, 10, 1),
        checked=("the ArcGIS root",),
        where=("https://example.org/arcgis/rest/services",),
        recheck_after_days=30,
        terms='the "no automated access" clause',
        reason="refused",
    )
    assert rows[1].shares == "closures" and all(row.is_row for row in rows)


def test_a_row_with_a_misspelt_field_is_refused_rather_than_read_without_it(tmp_path):
    """A `term` for `terms` would otherwise drop a refusal's quoted words without a sound."""
    with pytest.raises(ValueError, match=r"\[club_a.closures\]: \['term'\] is not a field of a note row"):
        _rows(tmp_path, '[club_a.closures]\nconfirmed = 2026-10-01\nchecked = ["x"]\nwhere = ["https://e.org"]\nterm = "no"\n')
    with pytest.raises(ValueError, match=r"\['confirmed'\] is not a field of a share row"):
        _rows(tmp_path, '[club_a.warnings]\nshares = "closures"\nconfirmed = 2026-10-01\n')


def test_a_club_and_type_written_twice_is_refused(tmp_path):
    import tomllib

    with pytest.raises(tomllib.TOMLDecodeError, match="Cannot declare"):
        _rows(tmp_path, '[club_a.warnings]\nshares = "closures"\n\n[club_a.warnings]\nshares = "closures"\n')


def test_a_confirmed_date_written_as_a_string_is_refused(tmp_path):
    with pytest.raises(ValueError, match=r"`confirmed` is '2026-10-01', which is not a date"):
        _rows(tmp_path, '[club_a.photos]\nconfirmed = "2026-10-01"\nchecked = ["x"]\nwhere = ["https://e.org"]\n')


def test_a_note_row_without_checked_or_where_reads_and_then_fails_the_shape_check(tmp_path):
    (row,) = _rows(tmp_path, "[club_a.photos]\nconfirmed = 2026-10-01\n")
    assert row.note.problems(date(2026, 10, 6)) == ["checked must list what was looked at", "where must list https URLs"]


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
    # A reviewed file is a path under reference/, or the registry itself, which _shared/registry/ lands whole.
    reviewed = {REGISTRY_PATH.relative_to(PIPELINE_DIR).as_posix()}
    unresolved = sorted(
        key
        for key in claims
        if key not in registry and key not in reviewed and not (key.startswith("reference/") and (PIPELINE_DIR / key).exists())
    )
    assert not unresolved, f"claims that are neither a sources.json key nor a reviewed file in git: {unresolved}"


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


#: Decision 61's conditions job, by raw table: the upstreams the conditions bake published before decision 53,
#: read off the conditions legs at 52835a44 (every other hourly resource there was a phase B layer of
#: 2026-10-03). Written out here as well as in HOURLY_JOB_TABLES, so that moving a source between the two
#: jobs is a change a reviewer sees twice, never a rename that quietly turns a closure four-hourly.
CONDITIONS_JOB_TABLES = frozenset(
    {
        "raw_nws__alerts",
        "raw_ourhike__closures",
        "raw_ourhike__reports",
        "raw_ourhike__notes",
        "raw_ourhike__disputes",
        "raw_ourhike__work_projects",
        "raw_atc__atc_updates",
        "raw_atc__atc_trail_updates",
        "raw_atc__atc_trail_updates_pages",
        "raw_nynjtc__nynjtc_trail_alerts",
        "raw_nynjtc__nynjtc_trail_alerts_terms",
        "raw_nysparks__oprhp_trail_closures",
    }
)


def test_the_conditions_job_keeps_exactly_the_sources_published_before_decision_53():
    assert set(HOURLY_JOB_TABLES) == CONDITIONS_JOB_TABLES
    assert all(reason.strip() for reason in HOURLY_JOB_TABLES.values()), "each table says why it stays hourly"


def test_every_hourly_lane_resource_is_read_by_exactly_one_job_and_each_named_table_exists():
    """The notices job is everything else on the lane, so a source wired later goes there without being named, and a
    named table that no resource lands (a rename) would silently move its source off the hourly job."""
    hourly = lane_resources("hourly", all_resources(EVERY_FILE))
    tables = {resource.table for resource in hourly}
    assert CONDITIONS_JOB_TABLES <= tables, f"named and not landed on the hourly lane: {sorted(CONDITIONS_JOB_TABLES - tables)}"
    conditions, notices = leg_tables("conditions_ua", hourly), leg_tables("notices_ua", hourly)
    assert conditions == CONDITIONS_JOB_TABLES
    assert not conditions & notices and conditions | notices == tables
    for name, leg in LEGS.items():
        assert leg_tables(name, hourly) == (conditions if leg.job == CONDITIONS_JOB else notices), name
    assert {leg.job for leg in LEGS.values()} == {CONDITIONS_JOB, NOTICES_JOB}


def test_ourhikes_own_rows_and_nws_never_wait_four_hours():
    """Decision 61's reason for the split: a verified closure within the hour, and a short warning before it expires."""
    for resource in all_resources(EVERY_FILE):
        if isinstance(resource, ConditionsQuery | NwsAlerts):
            assert job_of(resource) == CONDITIONS_JOB, resource.table


def test_no_table_is_written_by_two_resources_except_the_shared_org_table():
    tables = Counter(r.table for r in all_resources(EVERY_FILE))
    shared = sorted(table for table, n in tables.items() if n > 1 and table != ORGS_TABLE)
    assert not shared, f"tables two resources write: {shared}"
    lanes_by_table = {}
    for resource in all_resources(EVERY_FILE):
        lanes_by_table.setdefault(resource.table, set()).add(resource.cadence)
    assert all(len(lanes) == 1 for lanes in lanes_by_table.values()), "a table sits on one pipeline"


def test_every_raw_table_is_named_as_dlt_lands_it():
    # dlt normalizes a table_name as a path split on `__`; a name it would
    # rewrite lands under the rewritten name, and the run check, the
    # as-landed copy and dbt's sources all read the name as written. The
    # monthly lane's first run refused on exactly this: `3dep_13_current`
    # landed as `raw_usgs___3dep_13_current` (run 37058045092, 2026-10-02).
    from dlt.common.normalizers.naming import sql_ci_v1

    naming = sql_ci_v1.NamingConvention()
    renamed = sorted(
        (r.table, naming.normalize_path(r.table)) for r in all_resources(EVERY_FILE) if naming.normalize_path(r.table) != r.table
    )
    assert not renamed, f"tables dlt would land under another name: {renamed}"


def test_a_raw_table_key_that_starts_with_a_digit_is_refused():
    with pytest.raises(ValueError, match="may not start with a digit"):
        raw_table("usgs", "3dep_13_current")


def test_raw_table_names_keep_the_double_underscore():
    assert raw_table("nysdec", "dec_lean_tos") == "raw_nysdec__dec_lean_tos"
    assert raw_table("atc", "reference/water_distance.json") == "raw_atc__water_distance"
    assert raw_table("atc", "reference/challenges/atc") == "raw_atc__challenges_atc"
    assert raw_table("registry", "sources.json") == "raw_registry__sources"


def test_a_club_file_never_names_a_url_to_fetch():
    """Builders take keys. A URL in a club file is either a note's `where`, a SAME_AS copy, its docstring or a mistake.

    A club's notes are rows of not_available.toml, which no builder reads; _shared/'s three notes.py are the
    files left holding a note."""
    for club_file in PY_FILES:
        if club_file.note is not None:
            continue
        tree = ast.parse(club_file.path.read_text())
        strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        # The raw constant, not the cleaned text: get_docstring() strips the closing newline, so a docstring that
        # names a URL (a step-2 list of sources still to wire) never matched itself and read as a fetched URL.
        docstring = ast.get_docstring(tree, clean=False) or ""
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


def test_the_pipeline_suite_installs_the_pypdf_the_extract_job_runs():
    """requirements-dev.in pins pypdf at requirements-extract.txt's version, so the tests that read a real PDF run in
    CI (WF4 of the PR #1805 review): a pypdf bump that broke club_pdf_document_info would otherwise pass every suite
    and date GATC's water list by its HTTP date instead of its title's year."""

    def pin(path: Path) -> str | None:
        lines = [line for line in path.read_text().splitlines() if line.startswith("pypdf==")]
        assert len(lines) <= 1, path
        return lines[0].split("==")[1] if lines else None

    assert pin(PIPELINE_DIR / "requirements-extract.txt") is not None
    assert pin(PIPELINE_DIR / "requirements-dev.in") == pin(PIPELINE_DIR / "requirements-extract.txt")
    assert pin(PIPELINE_DIR / "requirements-dev.txt") == pin(PIPELINE_DIR / "requirements-extract.txt")


def _import_closure(start: list[Path]) -> tuple[set[Path], set[str]]:
    """(the local files reached, the third-party top-level names imported), following local modules from `start`.

    Read from the source rather than from sys.modules, because a pinned
    package's optional imports are its business: pyarrow imports numpy when
    numpy is installed, and the extract job runs without it.
    """

    def local(name: str) -> Path | None:
        parts = name.split(".")
        for candidate in (PIPELINE_DIR.joinpath(*parts).with_suffix(".py"), PIPELINE_DIR.joinpath(*parts, "__init__.py")):
            if candidate.exists():
                return candidate
        return None

    seen, outside, queue = set(), set(), list(start)
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
            else:
                continue
            for name in names:
                if found := local(name):
                    queue.append(found)
                elif not local(name.split(".")[0]) and name.split(".")[0] not in {"extract", "lib"}:
                    outside.add(name.split(".")[0])
    return seen, outside - set(sys.stdlib_module_names) - {"__future__"}


def _repository_imports(start: list[Path]) -> set[str]:
    """Top-level names the repository's own code imports, following its local modules from `start`."""
    return _import_closure(start)[1]


def test_every_module_the_extract_imports_is_pinned_in_its_own_requirements():
    """The extract job installs requirements-extract.txt and nothing else, so a club file must import nothing more.

    A fetcher's module pulled in for one constant brings its imports along:
    export_weather_alerts.py imports shapely, which is why the NWS endpoint and
    its check live in lib/nws_alerts.py. The pipeline suite's environment holds
    every build dependency, so without this a missing pin shows up first as
    the extract job failing at import.
    """
    from importlib.metadata import packages_distributions

    start = [*EXTRACT_DIR.glob("_*.py"), *(file.path for file in PY_FILES)]
    imported = _repository_imports(start)
    providers = packages_distributions()

    def canonical(name: str) -> str:
        return re.sub(r"[-_.]+", "-", name).lower()

    pinned = {
        canonical(match[1])
        for line in (PIPELINE_DIR / "requirements-extract.txt").read_text().splitlines()
        if (match := re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==", line))
    }
    assert {"dlt", "requests"} <= imported, "the walk did not reach the extract's own imports, so it checked nothing"
    unpinned = sorted(name for name in imported if not any(canonical(d) in pinned for d in providers.get(name, [name])))
    assert not unpinned, f"imported by the extract's code and not in requirements-extract.txt: {unpinned}"


def test_the_dbt_jobs_scope_covers_every_local_module_the_extract_imports():
    """pipeline-tests.yml's dbt job builds its warehouse through the extract (fixture mode) and checks parity with
    parity.py, so a change to any module either imports, or to a reviewed file fixture mode loads, must run that job.
    Its `paths:` list is hand-written, and this holds it to the import walk and to the reviewed files."""
    import yaml

    from extract._kinds import ReviewedDir, ReviewedFile

    workflow = yaml.safe_load((PIPELINE_DIR.parent / ".github" / "workflows" / "pipeline-tests.yml").read_text())
    scope = next(step for step in workflow["jobs"]["dbt"]["steps"] if step.get("id") == "scope")["with"]["paths"].split()
    reached, _ = _import_closure([*EXTRACT_DIR.glob("_*.py"), *(file.path for file in PY_FILES), PIPELINE_DIR / "parity.py"])
    # Read by discover(), so the warehouse fixture mode builds depends on them as much as on any module.
    reached |= {NOT_AVAILABLE_PATH, TRAIL_ORGS_PATH}
    reviewed = {
        PIPELINE_DIR / resource.path
        for resource in all_resources(discover() + discover_shared())
        if isinstance(resource, ReviewedFile | ReviewedDir)
    }
    uncovered = sorted(
        str(path.relative_to(PIPELINE_DIR.parent))
        for path in reached | reviewed
        if not any(str(path.relative_to(PIPELINE_DIR.parent)).startswith(prefix) for prefix in scope)
    )
    assert not uncovered, f"read by the dbt job and outside its paths: {uncovered}"


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


def test_every_aggregator_has_a_shared_folder_that_extracts_or_quotes_the_terms_that_refuse_it():
    """osm, outerspatial and avenza live in _shared/. osm's folder extracts its Geofabrik copies (#1652 — Download OSM's
    Geofabrik extracts at most once a month, into a private raw bucket that outlives the 7-day Actions cache); the other
    two are notes quoting the terms that refuse them."""
    orgs = _trail_orgs(TRAIL_ORGS_PATH)
    for slug in sorted(slug for slug, row in orgs.items() if row.get("type") == "aggregator"):
        folder = EXTRACT_DIR / "_shared" / folder_for_slug(slug)
        assert folder.is_dir(), f"{slug} has no _shared/ folder"
        claiming = [shared for shared in SHARED_FILES if shared.club == folder.name and shared.resources]
        if claiming:
            assert {key for shared in claiming for key in shared.claims} == {"osm_water"}, slug
            continue
        note = _shared_module(f"{folder_for_slug(slug)}/notes.py").NOT_AVAILABLE
        assert note.problems(TODAY) == [] and note.terms, f"{slug}'s note quotes the terms that refuse it"


def test_shared_folders_never_share_a_name_with_a_club_and_each_resource_names_its_type():
    """A _shared/ folder plays the club's part in `raw_<folder>__<key>`, so a shared name equal to a club's could collide.

    Every managing club, folder or not: a club with no resource file today may get one, and its folder that name."""
    clubs = managing_clubs()
    for shared in SHARED_FILES:
        assert shared.club not in clubs, f"_shared/{shared.club}/ has a club folder's name"
        if shared.resources:
            assert shared.type in TYPES, f"_shared/{shared.club}/{shared.path.name} declares no TYPE among {TYPES}"
            assert shared.claims or shared.unregistered, (
                f"_shared/{shared.club}/{shared.path.name} has resources, no CLAIMS, and no UNREGISTERED reason"
            )
