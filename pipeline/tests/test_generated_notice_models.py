"""The club notice sources' generated dbt models are what pipeline/generate_notice_models.py writes (decision 53, phase C).

The generator's output is not committed (decision 91): every place that
parses the dbt project writes it first, through generate_dbt.py, so a closures
or warnings resource registered in a club folder is staged by the next run.
tests/test_dbt_generated_staging.py holds, for both generators, that a run
writes the same bytes every time and that git commits none of them. The first
test here fails when the tree on disk, which the rest of the suite reads,
differs from what the generator writes now: a local run on a tree written
before the last registry edit, or a generated file edited by hand.

It also holds what the generated models rest on and the generator cannot
check by itself: every field the ArcGIS seed names is a field the layer's
measured field list holds; every hand-staged notice table is one the closures
family reads; no pub_ writer reads a club notice model except through the
marts; and a key two different raw rows share holds that source in the gate
rather than stopping every club's build.
"""

import csv
import re
from pathlib import Path

import pytest
import yaml

import generate_notice_models as generator
import make_dbt_fixtures

PIPELINE = Path(__file__).resolve().parent.parent
DBT = PIPELINE / "dbt"


@pytest.fixture(scope="module")
def files() -> dict[Path, str]:
    return generator.render_all()


def test_every_generated_file_is_what_the_generator_writes(files):
    problems = generator.differences(files)
    assert not problems, "run `python generate_dbt.py` from pipeline/, then the suite again:\n" + "\n".join(problems)


def test_the_generator_stages_every_notice_source_that_has_no_hand_written_model():
    sources = generator.notice_sources()
    generated = [source for source in sources if not source.hand_staged]
    assert generated, "no club notice source to stage"
    hand = {source.table for source in sources if source.hand_staged}
    # The hand-staged ones are exactly the closures family's own branches' tables.
    assert hand == {
        "raw_atc__atc_trail_updates",
        "raw_atc__atc_trail_updates_pages",
        "raw_atc__atc_updates",
        "raw_nynjtc__nynjtc_trail_alerts",
        "raw_nysparks__oprhp_trail_closures",
        "raw_nws__alerts",
        "raw_ourhike__closures",
        "raw_ourhike__disputes",
        "raw_ourhike__notes",
        "raw_ourhike__reports",
        "raw_ourhike__work_projects",
    }


def _seed(name: str) -> list[dict]:
    with (DBT / "seeds" / f"{name}.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_every_arcgis_field_the_seed_names_is_in_the_layers_measured_field_list():
    """make_dbt_fixtures.py's NOTICE_LAYERS rows carry each layer's field names as decision 53's inventory read them."""
    arcgis = {
        source.key for source in generator.notice_sources() if source.reader_class == "ArcgisLayer" and not source.hand_staged
    }
    rows = {row["source_key"]: row for row in _seed("notice_source_fields")}
    assert set(rows) == arcgis, "one notice_source_fields row per generated ArcGIS notice layer, and no other"
    for key, row in rows.items():
        measured = set(make_dbt_fixtures.NOTICE_LAYERS[key][1])
        for role in generator.ROLES:
            if row[role] and generator._literal(row[role]) is None:
                assert row[role] in measured, f"{key}: {role} names {row[role]!r}, which the layer's field list does not hold"


def _fixture_layer() -> "generator.NoticeSource":
    return generator.NoticeSource(
        club="fixture",
        type="warnings",
        key="fixture_layer",
        table="raw_fixture__fixture_layer",
        reader_class="ArcgisLayer",
        cadence="hourly",
        hand_staged=False,
        entry={"id_field": "GlobalID", "title": "Fixture layer"},
    )


def _fixture_fields(**roles: str) -> dict[str, dict]:
    return {"fixture_layer": {"source_key": "fixture_layer", **{role: "" for role in generator.ROLES}, **roles}}


def test_a_seed_value_in_single_quotes_is_staged_as_those_words_on_every_row_and_never_read_as_a_field():
    """Decision 95 (the maintainer's poll, 2026-10-06): a layer whose only title is a code a hiker cannot read (CPW's
    ACTIVITYCO, BBHCA or MLHCA) is titled in words the seed carries in single quotes. The staging model writes them
    as a SQL string, so every row of the layer carries them, and neither the wording union's fact columns nor a
    notice_field() call takes the words for a field the layer lands."""
    source = _fixture_layer()
    fields = _fixture_fields(title="'Fixture words'", category="'Fixture kind'", edited="EDIT_DATE")
    model = generator.render_stg(source, fields)
    assert "    'Fixture words' as title,\n" in model
    assert "    'Fixture kind' as category,\n" in model
    assert "{{ notice_instant(notice_field('edit_date')) }} as source_edited_at," in model
    assert "notice_field('fixture" not in model and "notice_field(''" not in model
    assert generator._fact_columns(source, fields) == ["edit_date", "globalid"]


@pytest.mark.parametrize("role", [role for role in generator.ROLES if role not in ("title", "category")])
def test_a_seed_value_in_single_quotes_for_a_status_a_date_a_link_or_a_place_stops_the_generator(role):
    """Only a title or a category may be words the seed supplies: a status, a date, a link or a place a source did
    not state would be OurHike's claim in the source's voice (miss rather than cry wolf)."""
    with pytest.raises(SystemExit, match=f"{role}.*single quotes"):
        generator.render_stg(_fixture_layer(), _fixture_fields(**{role: "'Fixture words'"}))


def test_cpw_conflict_areas_are_titled_in_decision_95s_words_and_never_by_their_activityco_code(files):
    """The maintainer's poll of 2026-10-06, option A: "Black bear conflict area" and "Mountain lion conflict area",
    category "Wildlife conflict area". Before it, all 613 bear rows and 266 lion rows read live on 2026-10-06 (fix
    worker B, PR #1805's round-2 review) staged their title from ACTIVITYCO, which is BBHCA or MLHCA on every row."""
    staging = DBT / "models" / "staging" / "cotrex" / "notices"
    for stem, title in (
        ("cpw_bear_conflict_areas", "Black bear conflict area"),
        ("cpw_lion_conflict_areas", "Mountain lion conflict area"),
    ):
        model = files[staging / f"stg_cotrex__{stem}.sql"]
        assert f"    '{title}' as title,\n" in model, stem
        assert "    'Wildlife conflict area' as category,\n" in model, stem
        assert "notice_field('activityco')" not in model, stem


def test_every_status_value_belongs_to_a_source_whose_seed_row_names_a_status_field():
    fields = {row["source_key"]: row for row in _seed("notice_source_fields")}
    readers = {source.key: source.reader for source in generator.notice_sources() if not source.hand_staged}
    for row in _seed("notice_status_values"):
        key = row["source_key"]
        has_status = bool(fields.get(key, {}).get("status")) or "status" in readers[key].roles
        assert has_status, f"{key}: a status value for a source whose status field is not staged"


def test_the_recreation_site_layer_stages_its_own_status_as_its_category(files):
    """Decision 78: USFS's `openstatus` is the recreation-site layer's category as well as its status.

    Before it the seed row left `category` empty, so all 3,123 of the layer's rows in UA's
    conditions/notices.json (soak run 536, 2026-10-05) read `category: null`, and the planned-hike
    panel showed a bare campground name. The value crosses as the Forest Service sends it, a field
    value and never wording; the phone decides its casing (chrome/PlannedNoticeList.tsx).
    """
    (row,) = [row for row in _seed("notice_source_fields") if row["source_key"] == "usfs_rec_opportunities_status"]
    assert row["category"] == row["status"] == "openstatus"
    model = files[DBT / "models" / "staging" / "usfs" / "notices" / "stg_usfs__usfs_rec_opportunities_status.sql"]
    assert "{{ notice_field('openstatus') }} as category," in model


def test_a_conflicting_key_holds_its_source_and_never_stops_the_build(files):
    """Every club notice source's exactness test warns, and the gate holds the source instead.

    A failing test on a raw table skips everything downstream of it, every
    conditions file included, so one club's conflicting rows would stop ATC's,
    NYNJTC's and NWS's too. The base model counts the conflict itself with the
    hash the test compares, the staging model carries the count, and
    int_closures__gate holds the source on it (its unit test
    int_closures__gate_reads_its_sources_from_the_registry_and_the_run_log has
    the case).
    """
    for path, text in files.items():
        if path.name.endswith("__sources.yml"):
            for source in yaml.safe_load(text)["sources"]:
                for table in source["tables"]:
                    (test,) = [t["duplicates_are_exact"] for t in table["data_tests"]]
                    assert test["config"]["severity"] == "warn", table["name"]
        elif path.name.startswith("base_"):
            version = re.search(r"notice_row_version\(\s*source\(\s*'[a-z0-9_]+',\s*'([a-z0-9_]+)'\s*\)\s*\)", text)
            assert version, f"{path.name} does not hash its raw rows with notice_row_version()"
            raw = re.search(r"notice_raw_table\(\s*source\(\s*'[a-z0-9_]+',\s*'([a-z0-9_]+)'\s*\)", text).group(1)
            assert version.group(1) == raw, f"{path.name} hashes {version.group(1)} but reads {raw}"
            assert "count(distinct keyed.row_version)" in text and "as key_versions" in text, path.name
        elif path.name.startswith("stg_"):
            assert "fields.key_versions," in text, f"{path.name} does not carry key_versions to the gate"
    gate = (DBT / "models" / "intermediate" / "closures" / "int_closures__gate.sql").read_text()
    assert "count(*) filter (where key_versions > 1) as rows_conflicting" in gate


def test_no_pub_writer_reads_a_club_notice_model_except_through_the_marts():
    """int_warnings__wording_leaks reads the club rows the marts are built from (before the gate since decision 81), so a
    writer that read a club notice model directly would go unchecked."""
    generated = {source.stg_model for source in generator.notice_sources() if not source.hand_staged}
    generated |= {source.base_model for source in generator.notice_sources() if not source.hand_staged}
    generated |= {
        "int_closures__club_notices",
        "int_closures__club_notices_unioned",
        "int_closures__window_carried",
        "int_closures__held_carried",
    }
    for path in (DBT / "models" / "publish").glob("pub_*.sql"):
        refs = set(re.findall(r"ref\('([a-z0-9_]+)'", path.read_text()))
        assert not refs & generated, f"{path.name} reads {sorted(refs & generated)}"


def test_the_readers_seed_marks_every_feed_a_window():
    for row in _seed("notice_readers"):
        assert (row["listing"] == "window") == (row["reader"] == "feed_notices"), row["raw_table"]


def test_only_a_pdf_notice_goes_without_freshness_and_each_has_its_evaluator_exception(files):
    """CI's `dbt source freshness` fails on a table the fixture warehouse never holds, and fixture mode lands no PDF.

    So a PDF page notice's table carries `freshness: null`, every other generated
    table keeps its source's, and each PDF one has its fct_sources_without_freshness
    row in seeds/dbt_project_evaluator_exceptions.csv, so the evaluator's rule still
    holds for the rest.
    """
    without = set()
    for path, text in files.items():
        if path.name.endswith("__sources.yml"):
            for source in yaml.safe_load(text)["sources"]:
                for table in source["tables"]:
                    if "freshness" in (table.get("config") or {}):
                        assert table["config"]["freshness"] is None, table["name"]
                        without.add(f"{source['name']}.{table['name']}")
    pdfs = {f"{s.club}.{s.table}" for s in generator.notice_sources() if not s.hand_staged and generator.is_pdf_notice(s)}
    assert without == pdfs
    excepted = {
        row["id_to_exclude"]
        for row in _seed("dbt_project_evaluator_exceptions")
        if row["fct_name"] == "fct_sources_without_freshness"
    }
    assert pdfs <= excepted, sorted(pdfs - excepted)


@pytest.mark.parametrize(("reader_class", "columns"), [("FeedNotices", "FEED_COLUMNS"), ("PageNotice", "PAGE_COLUMNS")])
def test_a_reader_no_source_uses_yet_stages_only_columns_it_lands(reader_class, columns):
    """No club source on 52835a44 reads a feed or a page, so no build runs these two shapes until one is registered.

    The other readers' shapes are run by the fixtures build through the sources
    that use them; these two are held to the reader's own column list here, so
    the first feed or page a club registers stages columns that exist.
    """
    from extract import _notices

    landed = set(getattr(_notices, columns))
    reader = generator.READERS[reader_class]
    named = {generator._column(spec)[0] for spec in reader.roles.values()} | set(reader.key)
    assert named <= landed, sorted(named - landed)
    assert reader.lists <= landed


def test_every_unit_test_input_on_a_generated_notice_model_is_sql_rows():
    """A generated notice base model reads its raw table through notice_raw_table(), so on a warehouse that lacks the
    table (an hourly build with no served notices copy, decision 61) it has only the key columns. dbt checks dict or
    CSV fixture rows against the input's real columns and fails the whole build before a test runs, which stopped the
    soak run on ecc43d56 (publish-conditions.yml 37203308446). SQL rows carry their own columns."""
    import glob

    import yaml

    import generate_notice_models

    bases = {source.base_model for source in generate_notice_models.notice_sources() if not source.hand_staged}
    offenders = []
    for path in glob.glob(str(Path(generate_notice_models.__file__).parent / "dbt" / "models" / "**" / "*.yml"), recursive=True):
        for unit_test in (yaml.safe_load(Path(path).read_text()) or {}).get("unit_tests") or []:
            for given in unit_test.get("given") or []:
                name = given.get("input", "").removeprefix("ref('").removesuffix("')")
                if name in bases and given.get("format", "dict") != "sql":
                    offenders.append(f"{unit_test['name']}: {name}")
    assert not offenders, offenders


def test_only_the_named_polygon_sources_base_models_are_tables(files):
    """generate_notice_models.py's TABLE_BASES: each is a generated, spatial notice source, and only its base model is a table.

    A key renamed in sources.json would otherwise leave its polygons hashed again by every test and union, silently.
    """
    sources = {source.key: source for source in generator.notice_sources() if not source.hand_staged}
    assert generator.TABLE_BASES <= set(sources), sorted(generator.TABLE_BASES - set(sources))
    assert all(sources[key].reader.spatial for key in generator.TABLE_BASES)
    tables = {
        path.stem
        for path, text in files.items()
        if path.name.startswith("base_") and path.suffix == ".sql" and "{{ config(materialized='table') }}" in text
    }
    assert tables == {sources[key].base_model for key in generator.TABLE_BASES}


def test_every_notice_source_that_reaches_hikers_lands_in_the_warehouse_of_the_lane_that_builds_its_readers():
    """Review finding ARC-1 of PR #1805 — dlt → dbt re-platform as one go/no-go change: CPW's bear and mountain lion
    conflict areas (613 and 266 polygons, `reaches_hikers: true`) were extracted on the monthly lane, by a
    `cadence_override="monthly"` from before decision 61 gave the notices job an hour to read. Their only readers are
    the unions this generator writes, which also read hourly sources, so they build on the hourly lane alone
    (build_marts.py's LANE_EXCLUDES keeps them out of the monthly build). The hourly build's warehouse holds a
    conditions leg's tables and a notices leg's served copy, never the monthly store, so int_closures__gate held both
    every hour as "not in this warehouse", and every run stayed green.

    So every staged notice source's table must be one a leg reads: decision 61's two jobs (extract/_run.py's
    leg_tables()). A source whose sources.json row says reaches_hikers false is let through, since the gate holds it
    either way: USFWS's hunt units today. Its row turning true turns this red, which is when its lane is decided."""
    from extract._contract import all_resources, discover, discover_shared
    from extract._run import LEGS, leg_tables

    resources = all_resources(discover() + discover_shared())
    hourly = set().union(*(leg_tables(leg, resources) for leg in LEGS))
    unread = {
        source.key: source.cadence
        for source in generator.notice_sources()
        if source.table not in hourly and (source.entry or {}).get("reaches_hikers") is not False
    }
    assert unread == {}, f"reach hikers and land where no build that reads them looks: {unread}"
    held = sorted(source.key for source in generator.notice_sources() if source.table not in hourly)
    assert held == ["fws_hunt_units"], "each one let through is held by its reaches_hikers false, and named here"
