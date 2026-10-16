"""The extract layout check, on every pull request: pipeline/ELT.md, "The data checks", check 1.

It holds the shape of what the extract reads and nothing about the network:
every managing organisation in trail_orgs.json answers each of the ten
FILE_TYPES exactly once, with registry rows (a sources.json row's `extract`
field, or a trail_orgs.json `reviewed_files` entry) or a row of
extract/not_available.toml, and has one catalogue row; every row is a
well-formed note or a share naming a sibling with resources; every claim
resolves to a registry key or a reviewed file, once; every resource is on a
lane. It checks a note's shape and never its age, so the calendar cannot turn
an unrelated pull request red (check 3, note ageing, is the monthly job's).

NOT_YET_EXTRACTED below is the registry keys no org reads yet, by name, so
the gap is a list a reviewer can read. When it is empty, "every sources.json
key is read" holds outright and the list goes.
"""

import ast
import inspect
import json
import re
import sys
import textwrap
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from requests_mock import ANY

from extract import _kinds
from extract._contract import (
    CADENCES,
    EXTRACT_DIR,
    FILE_TYPES,
    MAY_BE_EMPTY,
    NOT_AVAILABLE_FILE,
    NOT_CLUB_TYPES,
    PIPELINE_DIR,
    REGISTRY_PATH,
    TYPES,
    ClubFile,
    NotAvailable,
    Resource,
    all_resources,
    discover,
    discover_shared,
    folder_for_slug,
    raw_table,
    read_not_available,
    read_registry,
    slug_for_folder,
)
from extract._kinds import ORGS_TABLE, CatalogueRow, ConditionsQuery, NwsAlerts, _registry, _trail_orgs
from extract._run import CONDITIONS_JOB, HOURLY_JOB_TABLES, LANES, LEGS, NOTICES_JOB, job_of, lane_resources, leg_tables
from lib.socrata import dataset_url
from tests.test_extract_zero_proofs import KINDS, ZERO_KEY

TRAIL_ORGS_PATH = PIPELINE_DIR / "reference" / "trail_orgs.json"

# sources.json keys no org reads yet, each with what it waits on.
# Remove a key when a row's `extract` reads it; the test below fails in
# both directions, so a key cannot be claimed and listed here at once, and a
# new registry row must be claimed or listed.
NOT_YET_EXTRACTED = frozenset(
    {
        # Waiting on #1804 — fetch_drought.py fetches droughtmonitor.unl.edu/data/, a
        # path the Drought Monitor's robots.txt disallows for every user agent. The
        # extract does not rebuild a fetch robots.txt refuses.
        "usdm_drought",
        # Registered on 2026-10-15 for their terms (a layer a trail_orgs.json row names gets its own registry row,
        # with its terms read), held, and waiting on a resource that reads each. Whether a steward's own line joins
        # or replaces the line its host carries is #1709's reconciliation.
        "fl_state_parks_trails",
        "fta_fnst_line",
        "iata_official_trail_sections",
        "idpr_centennial_trail_route",
        "idpr_idaho_routes",
        "maricopa_parks_trail_segments",
        "mi_dnr_iron_belle_trail",
        "mo_state_parks_trail_routes",
        "montour_trail_route",
        "nett_trail_segments",
        "nys_canal_canalway_trail",
        "oprd_rec_trails",
        "rctc_rachel_carson_trail_geojson",
        "vtrans_lvrt_centerline",
        "wsprc_long_distance_trails",
    }
)

TODAY = date.today()
FILES = discover()
SHARED_FILES = discover_shared()
EVERY_FILE = FILES + SHARED_FILES
NOT_AVAILABLE_PATH = EXTRACT_DIR / NOT_AVAILABLE_FILE
#: The answers the registry gives: an org's sources.json rows (or reviewed files) for one type.
REGISTRY_ANSWERS = [f for f in FILES if f.path in (REGISTRY_PATH, TRAIL_ORGS_PATH) and f.type != "org"]
READING_CLUBS = sorted({f.club for f in REGISTRY_ANSWERS})
BY_CLUB: dict[str, list[ClubFile]] = {}
for _answer in FILES:
    BY_CLUB.setdefault(_answer.club, []).append(_answer)
ROWS = [f for f in FILES if f.is_row]
#: The answers that are Python files of their own: _shared/'s, the one place the extract keeps free-form files.
PY_FILES = [f for f in EVERY_FILE if f.path.suffix == ".py"]
REGISTRY_ROWS = [row for row in json.loads(REGISTRY_PATH.read_text())["sources"] if "extract" in row]


def managing_slugs() -> set[str]:
    return {slug for slug, row in _trail_orgs(TRAIL_ORGS_PATH).items() if row.get("type") not in NOT_CLUB_TYPES}


def managing_clubs() -> set[str]:
    return {folder_for_slug(slug) for slug in managing_slugs()}


def home(answer: ClubFile) -> str:
    """Where an answer is written, as a reader would look for it."""
    if answer.is_row:
        return f"{NOT_AVAILABLE_FILE} [{answer.club}.{answer.type}]"
    if answer.path.suffix == ".py":
        return f"_shared/{answer.club}/{answer.path.name}"
    if answer.type == "org":
        return f"{answer.club}'s catalogue row"
    return f"the registry's {answer.club}.{answer.type} rows"


def answer_problems(answers: list[ClubFile], managing: set[str]) -> list[str]:
    """Why the answers are not exactly one per managing club and FILE_TYPES type, or [] when they are.

    Each club and type is answered by its registry rows or its row of not_available.toml, never both and never
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
                problems.append(f"{club} x {type_}: answered by neither registry rows nor a [{club}.{type_}] row")
            elif len(found) > 1:
                problems.append(f"{club} x {type_}: answered {len(found)} times, by {' and by '.join(found)}")
    for (club, type_), found in sorted(homes.items()):
        if club not in managing:
            problems.append(f"{found[0]}: {club!r} is not a managing club in trail_orgs.json")
    return problems


def test_there_are_registry_answers_and_rows_to_check():
    """A layout test over zero answers or zero rows passes vacuously; this is the line that says so."""
    assert {"atc", "nysdec"} <= set(READING_CLUBS)
    assert len(REGISTRY_ROWS) > 700, f"sources.json gave {len(REGISTRY_ROWS)} rows with `extract`"
    assert len(ROWS) > 1000, f"{NOT_AVAILABLE_FILE} gave {len(ROWS)} rows"


def test_every_org_the_registry_reads_for_is_a_managing_organisation_in_trail_orgs():
    unknown = {club for club in READING_CLUBS if slug_for_folder(club) not in managing_slugs()}
    assert not unknown, f"`extract.org` values with no managing trail_orgs.json row: {sorted(unknown)}"


def test_every_managing_club_answers_every_type_exactly_once_by_registry_rows_or_a_row():
    """No club leaves a type unanswered, and none answers one twice."""
    problems = answer_problems(FILES, managing_clubs())
    assert not problems, "\n".join(problems)


def test_no_row_names_a_type_the_registry_also_reads_for_its_club():
    """The case the exactly-once test also catches, named on its own: a row left behind when the registry row landed."""
    read = {(f.club, f.type) for f in REGISTRY_ANSWERS}
    beside = sorted(f"{NOT_AVAILABLE_FILE} [{f.club}.{f.type}] beside registry rows" for f in ROWS if (f.club, f.type) in read)
    assert not beside, "retire the row when the registry row lands:\n" + "\n".join(beside)


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
        ClubFile(club="club_a", type="closures", path=REGISTRY_PATH, claims=("k",), resources=(resource,)),
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
        f"club_a x closures: answered 2 times, by the registry's club_a.closures rows and by {NOT_AVAILABLE_FILE} "
        "[club_a.closures]",
        "club_a x warnings: answered by neither registry rows nor a [club_a.warnings] row",
        f"{NOT_AVAILABLE_FILE} [not_a_club.photos]: 'not_a_club' is not a managing club in trail_orgs.json",
    ]


def test_folder_names_and_slugs_map_both_ways_exactly():
    """`-` is written `_`, which reverses only while no slug holds an underscore."""
    slugs = set(_trail_orgs(TRAIL_ORGS_PATH))
    assert not [slug for slug in slugs if "_" in slug]
    for slug in slugs:
        assert slug_for_folder(folder_for_slug(slug)) == slug


def test_no_org_has_a_folder_of_python_files_any_more():
    """Every org is read the same way, from its registry rows, so the extract holds no per-org folder: only its own
    modules, not_available.toml and _shared/. A folder left behind would be read by nothing and look as if it were."""
    folders = sorted(p.name for p in EXTRACT_DIR.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))
    assert not [f for f in folders if any(child.suffix == ".py" for child in (EXTRACT_DIR / f).iterdir())], folders


@pytest.mark.parametrize("row", REGISTRY_ROWS, ids=lambda row: row["key"])
def test_every_registry_row_the_extract_reads_yields_one_resource_per_read_in_its_org_and_type(row):
    """The loader's whole contract, row by row: `extract.reads` has n entries, so n resources, each placed in the row's
    org and type and landing in `raw_<org>__<key>` (a second read of one key differs by its part, so by its table)."""
    spec = row["extract"]
    assert spec["type"] in FILE_TYPES, f"{row['key']}: `extract.type` {spec['type']!r} is not one of {FILE_TYPES}"
    (answer,) = [f for f in REGISTRY_ANSWERS if (f.club, f.type) == (spec["org"], spec["type"])]
    mine = [r for r in answer.resources if r.key == row["key"]]
    assert len(mine) == len(spec["reads"]) >= 1, row["key"]
    for resource in mine:
        assert (resource.club, resource.type) == (spec["org"], spec["type"])
        assert resource.table.startswith(raw_table(spec["org"], row["key"]))
    assert answer.claims.count(row["key"]) == 1


def test_every_registry_row_the_extract_reads_says_where_its_data_comes_from_in_plain_words():
    """A row's `notes` is its provenance: what the source is, when it was read, and what a hiker's safety turns on.
    It names the choice it rests on, never a decision number a reader would have to look up."""
    missing = sorted(row["key"] for row in REGISTRY_ROWS if not (row.get("notes") or "").strip())
    assert not missing, f"rows the extract reads with no `notes`: {missing}"
    numbered = sorted(row["key"] for row in REGISTRY_ROWS if re.search(r"\b[Dd]ecisions? \d", row.get("notes") or ""))
    assert not numbered, f"notes citing a decision number rather than stating the choice: {numbered}"


def test_no_not_available_row_cites_a_decision_number_or_a_deleted_club_file():
    """A note states the choice it rests on, and names a club's answer as <folder>.<type> (the file's header says so):
    the per-org files are gone, so a path like `nps/warnings.py` leads nowhere."""
    text = NOT_AVAILABLE_PATH.read_text(encoding="utf-8")
    assert not re.findall(r"\b[Dd]ecisions? \d", text)
    types = "|".join(FILE_TYPES)
    assert not re.findall(rf"(?<![\w/])[a-z][a-z_]*/(?:{types})\.py\b", text)


def test_every_read_names_a_reader_and_no_url():
    """Builders take keys: an option holding a URL would fetch an upstream the registry row does not register."""
    from extract._readers import READERS

    reads = [(row["key"], read) for row in REGISTRY_ROWS for read in row["extract"]["reads"]]
    reads += [
        (entry["path"], read)
        for org in _trail_orgs(TRAIL_ORGS_PATH).values()
        for entry in org.get("reviewed_files", ())
        for read in entry["reads"]
    ]
    for key, read in reads:
        assert read.get("reader") in READERS, f"{key}: {read.get('reader')!r} is not a reader"
        urls = [value for value in read.values() if isinstance(value, str) and re.search(r"https?://", value)]
        assert not urls, f"{key}: a read's options hold a URL: {urls}"


def _registry_file(tmp_path, extract: dict) -> Path:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": [{"key": "centerline", "url": "https://example.org/x", "extract": extract}]}))
    orgs = tmp_path / "trail_orgs.json"
    orgs.write_text(json.dumps({"orgs": []}))
    return path


def test_a_misspelt_extract_field_or_an_unknown_reader_is_refused_rather_than_read_as_nothing(tmp_path):
    reads = [{"reader": "arcgis_layer"}]
    with pytest.raises(ValueError, match=r"centerline: \['read'\] is not a field of `extract`"):
        read_registry(
            _registry_file(tmp_path, {"org": "atc", "type": "trail_lines", "read": reads}), tmp_path / "trail_orgs.json"
        )
    with pytest.raises(ValueError, match=r"centerline: reader 'arcgis' is not one of"):
        read_registry(
            _registry_file(tmp_path, {"org": "atc", "type": "trail_lines", "reads": [{"reader": "arcgis"}]}),
            tmp_path / "trail_orgs.json",
        )


def test_a_reads_options_become_the_builders_keyword_arguments_and_a_list_becomes_a_tuple(tmp_path):
    extract = {
        "org": "atc",
        "type": "trail_lines",
        "reads": [{"reader": "arcgis_layer", "cadence_override": "daily", "cadence_reason": "why"}],
    }
    (answer,) = read_registry(_registry_file(tmp_path, extract), tmp_path / "trail_orgs.json")
    (resource,) = answer.resources
    assert (resource.club, resource.type, resource.cadence, resource.table) == (
        "atc",
        "trail_lines",
        "daily",
        "raw_atc__centerline",
    )
    from extract._readers import _value

    assert _value("category_slugs", ["a", "b"]) == ("a", "b")


def test_a_date_pattern_may_name_the_shared_date_regex_rather_than_repeat_it():
    from extract._notices import DATE
    from extract._readers import _value

    assert _value("date_pattern", r"\({DATE}\)") == r"\(" + DATE + r"\)"


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
def test_a_share_names_a_sibling_type_whose_registry_rows_have_resources(club_file):
    sibling = next((f for f in BY_CLUB[club_file.club] if f.type == club_file.shares and not f.is_row), None)
    assert sibling is not None and sibling.form == "claims" and sibling.resources, (
        f"{home(club_file)} shares {club_file.shares!r}, which the registry reads nothing for"
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
        # A key may feed two resources (NYNJTC's alerts: posts and terms), so the sets must match. A key the file no
        # longer reads is KEPT instead (extract/_contract.py's Kept), and never both.
        read = {r.key for r in club_file.resources}
        kept = {k.key for k in club_file.kept}
        assert not read & kept, f"{home(club_file)}: {sorted(read & kept)} both read and KEPT"
        assert sorted(set(club_file.claims)) == sorted(read | kept), (
            f"{home(club_file)}: CLAIMS must match the RESOURCES' keys and the KEPT keys"
        )


#: Every claimed key no lane reads any more, with the file that keeps it (extract/_contract.py's Kept).
KEPT = [(club_file, kept) for club_file in EVERY_FILE for kept in club_file.kept]


def test_census_tiger_states_is_kept_because_its_robots_txt_refuses_every_agent():
    """The maintainer's poll of 2026-10-10 on ELT.md's open question 16, "Keep the last copy": www2.census.gov's
    robots.txt puts `*` in RavenCrawler's `Disallow: /` group, so the key is kept, not read. Also the line that says
    the parametrized checks below have something to check."""
    assert {kept.key for _, kept in KEPT} >= {"census_tiger_states"}


@pytest.mark.parametrize(("club_file", "kept"), KEPT, ids=[kept.key for _, kept in KEPT])
def test_a_kept_key_is_read_by_no_lane_and_its_note_says_why_and_when_to_look_again(club_file, kept):
    from extract._contract import Kept

    assert isinstance(kept, Kept) and isinstance(kept.note, NotAvailable)
    assert kept.key in club_file.claims, f"{club_file.path}: a KEPT key is still claimed by the file that read it"
    assert kept.key in _registry(REGISTRY_PATH), f"{kept.key}: kept, so its sources.json row stays"
    resources = all_resources(EVERY_FILE)
    assert kept.key not in {resource.key for resource in resources}, f"{kept.key} is kept, so no resource may read it"
    assert raw_table(club_file.club, kept.key) not in {resource.table for resource in resources}
    assert kept.note.problems(TODAY) == []
    assert kept.note.terms and kept.note.terms.strip(), f"{kept.key}: `terms` quotes what refused it, verbatim"
    assert kept.note.reason and kept.note.reason.strip(), f"{kept.key}: `reason` says why the last copy may stand in"


def test_the_kept_census_note_quotes_a_robots_txt_that_refuses_our_agent_the_tiger_file():
    """The quoted lines are the refusal itself: read by extract/_robots.py's own parser, they disallow the file for
    USER_AGENT's product token, so a quote edited into something that would let us in fails here."""
    from extract import _robots

    (kept,) = [kept for _, kept in KEPT if kept.key == "census_tiger_states"]
    rules, _ = _robots.parse(kept.note.terms)
    url = _registry(REGISTRY_PATH)["census_tiger_states"]["url"]
    assert not _robots.Robots(rules).allows(url)


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


def test_a_resource_whose_rows_are_another_types_names_one_that_may_not_empty_and_says_why():
    """Resource.holds judges a table as another type's in the run check, emptiness and the shrink floor, while its
    lane stays its file's: FDEP's park boundaries, a places layer on the closures lane (review finding S1-2 of
    2026-10-15). It may only take that allowance away. Emptiness is granted by a notice file's own type, so a
    `holds` naming closures or warnings would let a layer of any other kind land empty."""
    holding = [resource for resource in all_resources(EVERY_FILE) if resource.holds is not None]
    assert "fl_state_parks_park_boundaries" in {resource.key for resource in holding}
    for resource in holding:
        assert resource.holds in FILE_TYPES and resource.holds != resource.type, resource.table
        assert resource.holds not in MAY_BE_EMPTY, f"{resource.table}: holds may only refuse emptiness"
        assert resource.holds_reason, f"{resource.table}: holds needs holds_reason"
        assert not resource.may_be_empty, f"{resource.table}: its rows are {resource.holds}, which may not empty"


#: The conditions job, by raw table: the upstreams the conditions bake published before the club notices were
#: added, read off the conditions legs at 52835a44. Written out here as well as in HOURLY_JOB_TABLES, so that moving a source between the two
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


def test_the_conditions_job_keeps_exactly_the_sources_the_conditions_bake_published():
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
    """The reason for the split: a verified closure within the hour, and a short warning before it expires."""
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


#: WHETHER EACH READER KIND'S ROWS CARRY A `geometry` COLUMN, which the dlt
#: skill's rule 1 holds to a JSON hint: dlt creates no column it never saw a
#: value for, so a geometry null on every row of a first load lands no column
#: and the base model reading it fails (measured on SocrataDataset,
#: 2026-10-09). Every kind is named, so a new one is refused until somebody
#: says, as tests/test_extract_zero_proofs.py's READS_UPSTREAM_COUNT refuses one.
YIELDS_GEOMETRY = {
    "ArcgisLayer": True,
    "AtcTrailUpdatePages": False,
    "BucketListing": False,
    "CatalogueRow": False,
    "ClubPdf": False,
    "ConditionsQuery": False,  # a closure's endpoints and a report's place land as lat and lon columns
    "ContentPages": False,
    "ContentPdf": False,
    "ContentSheet": False,
    "DcnrParkAdvisories": False,
    "FeedNotices": False,
    "GeofabrikExtracts": False,
    "GisFile": True,
    "GuidePages": False,
    "HydrographyWatch": False,  # its `geometry` is the envelope it asks 3DHP about, a request parameter
    "JsonFeatures": True,
    "MediawikiAnnouncements": False,
    "MediawikiTemplatePages": False,
    "MyMapsPlacemarks": True,
    "NpsAlerts": False,  # no alert carries geometry: a park code is the place
    "NpsContent": False,
    "NpsRoadEvents": True,
    "NwsAlerts": True,
    "OgcFeatures": True,
    "OpentrailFeed": True,
    "PageNotice": False,
    "PagePoints": True,
    "PdfPoints": True,
    "PodcastEpisodes": False,
    "PodcastFeed": False,
    "PublishedHikes": False,  # a hike's track lands as the GPX it was served as, in `gpx`
    "ReviewedDir": False,  # a reviewed file's rows are its own, and none carries one (read 2026-10-09)
    "ReviewedFile": False,
    "SheetCsvSegments": False,
    "SiteTerms": False,
    "SocrataDataset": True,
    "UsgsElevatedVolcanoes": False,
    "WordpressChildPages": False,
    "WordpressPosts": False,
    "WordpressTerms": False,
}


@pytest.fixture
def zero_key_registry(tmp_path, monkeypatch):
    """A sources.json holding ZERO_KEY alone, in place of the real one, so every kind can be built on it."""
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": [{"key": ZERO_KEY, "url": "https://example.org/zero/"}]}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield
    _kinds._registry.cache_clear()


def test_every_reader_kind_says_whether_its_rows_carry_a_geometry_column():
    assert {kind.__name__ for kind in KINDS} == set(YIELDS_GEOMETRY), "add the kind to YIELDS_GEOMETRY"


@pytest.mark.usefixtures("zero_key_registry")
@pytest.mark.parametrize("kind", [kind for kind in KINDS if YIELDS_GEOMETRY.get(kind.__name__)], ids=lambda kind: kind.__name__)
def test_every_kind_whose_rows_carry_a_geometry_column_hints_it_as_json(kind, requests_mock):
    requests_mock.get(ANY, json={"fields": []})  # ArcgisLayer reads its hints from the layer's metadata
    hints = kind(key=ZERO_KEY, club="testclub", type="points_of_interest").column_hints()
    assert hints.get("geometry") == {"data_type": "json"}, f"{kind.__name__} yields `geometry` and does not hint it"


@pytest.mark.parametrize(
    "kind", [kind for kind in KINDS if not YIELDS_GEOMETRY.get(kind.__name__)], ids=lambda kind: kind.__name__
)
def test_a_kind_whose_own_code_sets_a_rows_geometry_is_one_that_yields_it(kind):
    """The table's backstop, for the commonest way to yield one: `row["geometry"] = …` in the kind's own class. A kind
    that builds its rows in its module's functions is the table's to answer for."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(kind)))
    sets = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "geometry"
    ]
    assert not sets, f"{kind.__name__} sets a row's `geometry`: mark it in YIELDS_GEOMETRY and hint it as json"


def test_a_shared_file_never_names_a_url_to_fetch():
    """Builders take keys. A URL in a _shared/ file is either a note's `where`, a SAME_AS copy, a KEPT key's note, its
    docstring or a mistake.

    _shared/'s three notes.py are the files holding a note. A KEPT key's note (extract/_contract.py's Kept) is read by
    no builder either: its `checked` and `where` say what a person read, and no lane reads the key."""
    for club_file in PY_FILES:
        if club_file.note is not None:
            continue
        tree = ast.parse(club_file.path.read_text())
        strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        # The raw constant, not the cleaned text: get_docstring() strips the closing newline, so a docstring that
        # names a URL (a step-2 list of sources still to wire) never matched itself and read as a fetched URL.
        docstring = ast.get_docstring(tree, clean=False) or ""
        copies = {url for note in club_file.same_as for url in note.copy}
        kept = {text for kept in club_file.kept for text in (*kept.note.checked, *kept.note.where)}
        urls = [s for s in strings if s != docstring and s not in copies | kept and re.search(r"https?://", s)]
        assert not urls, f"{home(club_file)} holds a URL outside its docstring: {urls}"


@pytest.mark.parametrize("club_file", [f for f in FILES if f.same_as], ids=lambda f: f"{f.club}/{f.type}")
def test_a_same_as_note_is_well_formed_and_its_original_is_claimed(club_file):
    claimed = {key for f in EVERY_FILE for key in f.claims}
    for note in club_file.same_as:
        assert note.problems(TODAY) == []
        assert note.original in claimed, f"{home(club_file)}: same_as original {note.original!r} is not claimed"


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
    """Each upstream dataset is landed once, under its steward."""
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
        # `.split()[0]`: in a hashed requirements file the pin line ends in a backslash.
        return lines[0].split("==")[1].split()[0] if lines else None

    assert pin(PIPELINE_DIR / "requirements-extract.txt") is not None
    assert pin(PIPELINE_DIR / "requirements-dev.in") == pin(PIPELINE_DIR / "requirements-extract.txt")
    assert pin(PIPELINE_DIR / "requirements-dev.txt") == pin(PIPELINE_DIR / "requirements-extract.txt")


@pytest.mark.parametrize("package", ["xlrd", "openpyxl", "defusedxml"])
def test_the_pipeline_suite_installs_the_workbook_readers_the_extract_job_runs(package):
    """requirements-dev.in pins each workbook reader at requirements-extract.txt's version, as it does pypdf's, so
    tests/test_extract_sheet_content.py opens a workbook with the reader the monthly extract job opens SMHC's and WMC's
    with (extract/_sheet_content.py), and through the XML parser that job's openpyxl uses (defusedxml)."""

    def pin(path: Path) -> str | None:
        lines = [line for line in path.read_text().splitlines() if line.startswith(f"{package}==")]
        assert len(lines) <= 1, path
        return lines[0].split("==")[1].split()[0] if lines else None

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
    reached |= {NOT_AVAILABLE_PATH, TRAIL_ORGS_PATH, REGISTRY_PATH}
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
    """A trail_orgs.json row that is not a managing club is still accounted for, so a survey never spends a search on
    it twice."""
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
