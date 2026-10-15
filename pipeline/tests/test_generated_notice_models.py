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
rather than stopping every club's build. And for a steward's own areas
(seeds/notice_steward_areas.csv, the maintainer's answer to Q3 of the poll of
2026-10-11): each link joins a notice source to its own steward's layer, the
layer rides a notices leg, and it is staged as areas, never as notices.
"""

import csv
import json
import re
from pathlib import Path

import pytest
import yaml

import generate_notice_models as generator
import make_dbt_fixtures
import make_dbt_staging

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
    generated = {source.key: source for source in generator.notice_sources() if not source.hand_staged}
    arcgis = {key for key, source in generated.items() if source.reader_class == "ArcgisLayer"}
    rows = {row["source_key"]: row for row in _seed("notice_source_fields")}
    assert arcgis <= set(rows), "one notice_source_fields row per generated ArcGIS notice layer"
    assert set(rows) <= set(generated), "a notice_source_fields row for a source the generator does not stage"
    for key, row in rows.items():
        if key not in arcgis:
            continue
        measured = set(make_dbt_fixtures.NOTICE_LAYERS[key][1])
        for role in generator.ROLES:
            if row[role] and generator._literal(row[role]) is None:
                assert row[role] in measured, f"{key}: {role} names {row[role]!r}, which the layer's field list does not hold"


def _fixture_posts(key: str) -> list[dict]:
    """A WordPress notice source's fixture posts, whose field names are the ones its live route served
    (make_dbt_fixtures.py's _club_wordpress_fixtures())."""
    document = json.loads(make_dbt_fixtures.closures_and_warnings_fixtures()[f"conditions/{key}.json"])
    posts = list(document.get("posts") or [])
    for typed in (document.get("types") or {}).values():
        posts += typed
    return posts


def test_every_field_a_seed_row_names_beyond_a_readers_shape_is_on_every_fixture_post():
    """The generator's ONE EXCEPTION TO A FIXED SHAPE: a source another reader lands names fields of the site's own
    (the Great Allegheny Passage's ACF `status` and `visibility`), so each must be a field its rows carry. A name its
    posts do not carry would stage as null on every row, and the maintainer's P6 answer would read nothing."""
    readers = {source.key: source for source in generator.notice_sources() if not source.hand_staged}
    others = [row for row in _seed("notice_source_fields") if readers[row["source_key"]].reader_class != "ArcgisLayer"]
    assert [row["source_key"] for row in others] == ["gap_trail_alerts"]
    for row in others:
        posts = _fixture_posts(row["source_key"])
        assert posts, row["source_key"]
        for role in generator.ROLES:
            if not row[role] or generator._literal(row[role]) is not None:
                continue
            column, path = generator._column(row[role])
            assert path is not None and re.fullmatch(r"\$\.[a-z_]+", path), (role, row[role])
            for post in posts:
                assert path.removeprefix("$.") in (post.get(column) or {}), (row["source_key"], role, row[role], post["id"])


def test_the_gap_alerts_stage_their_visibility_as_the_status_and_their_own_status_as_the_category(files):
    """The maintainer's answer to page 01's P6 (poll of 2026-10-11): an alert marked Hidden and one marked Cleared are
    both not current. The marks are ACF fields, read where the posts carry them and never out of a title."""
    model = files[DBT / "models" / "staging" / "gap" / "notices" / "stg_gap__gap_trail_alerts.sql"]
    assert "    {{ notice_field('acf', '$.visibility') }} as status,\n" in model
    assert "    {{ notice_field('acf', '$.status') }} as category,\n" in model
    assert "    {{ notice_field('title', '$.rendered') }} as title,\n" in model


def test_a_seed_value_in_single_quotes_for_another_readers_status_stops_the_generator():
    """A status OurHike supplied would be a claim in the source's voice, for a WordPress source as for a layer."""
    source = generator.NoticeSource(
        club="fixture",
        type="closures",
        key="fixture_posts",
        table="raw_fixture__fixture_posts",
        reader_class="WordpressPosts",
        cadence="hourly",
        hand_staged=False,
        entry={"title": "Fixture posts"},
    )
    fields = {"fixture_posts": {"source_key": "fixture_posts", **{role: "" for role in generator.ROLES}, "status": "'Closed'"}}
    with pytest.raises(SystemExit, match="status.*single quotes"):
        generator.render_stg(source, fields)


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


def test_a_narrative_is_staged_to_be_read_and_never_counted_as_a_fact(files):
    """Decision 190 reads IDPR's orders by their own words, and 4 of its 5 motorized-only route orders say so only in
    their Narrative (read live 2026-10-14), so the seed names that field and the generator stages it (PROSE_ROLES).
    It stays wording: _fact_columns() leaves it out, so int_warnings__notice_wording_unioned still collects it and
    int_warnings__wording_leaks still holds a source whose mart rows carry it. A source that names none stages a
    null narrative."""
    assert generator.PROSE_ROLES <= set(generator.ROLES)
    fields = {row["source_key"]: row for row in _seed("notice_source_fields")}
    named = {key for key, row in fields.items() if row["narrative"]}
    assert named == {
        "idpr_emergency_route_closures",
        "idpr_area_restrictions",
        "mi_dnr_trail_temporary_closures",
        "mi_dnr_trail_temporary_reroutes",
    }
    sources = {source.key: source for source in generator.notice_sources()}
    for key in named:
        source = sources[key]
        assert "narrative" not in generator._fact_columns(source, fields), key
        model = files[DBT / "models" / "staging" / source.club / "notices" / f"{source.stg_model}.sql"]
        field = fields[key]["narrative"].lower()
        assert f"    {{{{ notice_field('{field}') }}}} as narrative,\n" in model, key
    vtrans = sources["vtrans_rail_trail_closures"]
    model = files[DBT / "models" / "staging" / vtrans.club / "notices" / f"{vtrans.stg_model}.sql"]
    assert "    cast(null as varchar) as narrative,\n" in model


def test_a_season_is_staged_to_be_read_and_never_counted_as_a_fact(files):
    """Rule 1 of int_closures__club_notices reads a period a source states recurs every year (pipeline/ELT.md, status
    rule 4; the review of 2026-10-15, S1-3), and COTREX states it only in its Closure_Period, beside last season's
    dates: 'December 1 - April 30', or a sentence ('December 1 - April 15. May be extended to April 30'). So the seed
    names that field as COTREX's `season`, the generator stages it as prose (PROSE_ROLES), which the wording union
    still collects, and every other source stages a null season."""
    assert "season" in generator.PROSE_ROLES and "season" in generator.ROLES
    fields = {row["source_key"]: row for row in _seed("notice_source_fields")}
    named = {key for key, row in fields.items() if row["season"]}
    assert named == {"cotrex_seasonal_closures"}
    sources = {source.key: source for source in generator.notice_sources()}
    cotrex = sources["cotrex_seasonal_closures"]
    assert "closure_period" not in generator._fact_columns(cotrex, fields)
    model = files[DBT / "models" / "staging" / cotrex.club / "notices" / f"{cotrex.stg_model}.sql"]
    assert "    {{ notice_field('closure_period') }} as season,\n" in model
    idpr = sources["idpr_emergency_route_closures"]
    model = files[DBT / "models" / "staging" / idpr.club / "notices" / f"{idpr.stg_model}.sql"]
    assert "    cast(null as varchar) as season,\n" in model


def test_every_override_belongs_to_a_source_that_stages_the_field_it_names():
    """seeds/notice_word_overrides.csv reads a value in one field of one source; a field the source does not stage
    would read nothing, and the row would only look like a reading."""
    fields = {row["source_key"]: row for row in _seed("notice_source_fields")}
    readers = {source.key: source.reader for source in generator.notice_sources() if not source.hand_staged}
    for row in _seed("notice_word_overrides"):
        key = row["source_key"]
        spec = fields.get(key, {}).get(row["read_in"]) or readers[key].roles.get(row["read_in"])
        assert spec and generator._literal(spec) is None, f"{key}: an override for a field the source does not stage"


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


def test_a_layers_own_name_and_a_sites_own_type_are_staged_as_schema(files):
    """The maintainer's fixes of 2026-10-15 read a layer's own name (whether it says closures, or names a kind of
    site) and a site's own type. The name is the seed's `layer_title`, a constant on every row of every ArcGIS
    layer; the type is USFS's markeractivity, staged as `site_type` beside its category, which stays its openstatus
    (decision 78). A source the seed names no layer for stages a null name."""
    fields = {row["source_key"]: row for row in _seed("notice_source_fields")}
    sources = {source.key: source for source in generator.notice_sources()}
    arcgis = [key for key, source in sources.items() if source.reader_class == "ArcgisLayer" and not source.hand_staged]
    assert all(fields[key]["layer_title"] for key in arcgis), [key for key in arcgis if not fields[key]["layer_title"]]
    for key in ("idpr_emergency_route_closures", "usfs_rec_opportunities_status", "gap_trail_alerts"):
        source = sources[key]
        model = files[DBT / "models" / "staging" / source.club / "notices" / f"{source.stg_model}.sql"]
        title = fields[key]["layer_title"]
        line = f"    '{title}' as layer_title,\n" if title else "    cast(null as varchar) as layer_title,\n"
        assert line in model, key
    rec = sources["usfs_rec_opportunities_status"]
    model = files[DBT / "models" / "staging" / rec.club / "notices" / f"{rec.stg_model}.sql"]
    assert "    {{ notice_field('markeractivity') }} as site_type,\n" in model
    assert "{{ notice_field('openstatus') }} as category," in model
    assert {key for key, row in fields.items() if row["site_type"]} == {
        "usfs_rec_opportunities_status",
        "mo_state_parks_katy_trailheads",
        "blm_or_rec_site_status",
    }


def test_a_category_holds_a_status_or_a_reason_and_never_a_class_code():
    """The review of PR #1805 of 2026-10-15, thread 4279218690: a category prints under a notice's tag as "Listed as"
    its value (decisions 78 and 137), so Midpen's CLOSETYPE printed 'Regular' under a Closure tag on 122 closed areas,
    which a hiker reads as open. The standard (seeds/_notices__seeds.yml): a category holds the row's own status, the
    kind of notice its source files it as, or the reason it was posted, and never a class along another axis. Every
    seed row and every fixed reader that stages a category says which it holds, so a field is checked against the
    standard when it is named. The review's four: Midpen's category is its status, Wisconsin's its Reason, Santa
    Clara's none, and Michigan's its foot-travel status, with TrailUseCategory read as the narrative."""
    rows = _seed("notice_source_fields")
    for row in rows:
        if row["category"]:
            assert row["category_holds"] in ("status", "reason"), row["source_key"]
        else:
            assert row["category_holds"] == "", row["source_key"]
    for name, reader in generator.READERS.items():
        if "category" in reader.roles:
            assert reader.category_holds in ("status", "reason"), name
        else:
            assert reader.category_holds == "", name
    fields = {row["source_key"]: row for row in rows}
    assert fields["midpen_preserve_access"]["category"] == fields["midpen_preserve_access"]["status"] == "ACCESS"
    assert (fields["wi_dnr_park_closures"]["category"], fields["wi_dnr_park_closures"]["category_holds"]) == (
        "Reason",
        "reason",
    )
    assert fields["scc_parks_closed_areas"]["category"] == ""
    for key in ("mi_dnr_trail_temporary_closures", "mi_dnr_trail_temporary_reroutes"):
        assert fields[key]["category"] == fields[key]["status"] == "OpenClosedStatusNonmotor", key
        assert fields[key]["narrative"] == "TrailUseCategory", key


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
                    (test,) = [t["duplicates_are_exact"] for t in table["data_tests"] if "duplicates_are_exact" in t]
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


def test_the_wording_union_reads_every_generated_notice_source(files):
    """Decision 107 (the maintainer's poll, 2026-10-08): a club's closure post publishes as facts and a link, never the
    post's words. int_warnings__wording_leaks is what holds a source whose published row carries its own words, and it
    knows a source's words only from int_warnings__notice_wording_unioned, so a notice source that union leaves out
    could publish its paragraphs unchecked. 264 generated sources and 264 read, on 2026-10-08 at 4ad88f3b."""
    generated = {source.key for source in generator.notice_sources() if not source.hand_staged}
    read = set()
    for path, text in files.items():
        if path.name.startswith(generator.WORDING_MODEL.stem.removesuffix("_unioned") + "_part_"):
            read |= set(re.findall(r"^        '([a-z0-9_]+)' as source_key,$", text, re.MULTILINE))
    assert read == generated, {"left out": sorted(generated - read), "not a notice source": sorted(read - generated)}


def test_the_readers_seed_marks_every_feed_a_window():
    for row in _seed("notice_readers"):
        assert (row["listing"] == "window") == (row["reader"] == "feed_notices"), row["raw_table"]


def test_every_pdf_notice_keeps_its_freshness_and_only_cis_two_freshness_commands_leave_it_out(files):
    """The review of PR #1805 (dlt → dbt re-platform as one go/no-go change), 2026-10-09: the four PDF notices, each
    reaching hikers, carried `freshness: null`, and dbt 2.0.6 leaves such a source out of `source freshness` without a
    word, so production never turned one red. Fixture mode lands no PDF, because PageNotice reads one through pypdf
    and CI's dbt and pipeline jobs do not install it, so CI cannot measure them.

    So every generated notice table carries freshness (generator.notice_freshness(), which
    tests/test_notice_source_freshness.py holds), exactly the PDF notices carry generator.PDF_NOTICE_TAG, CI's two
    `dbt source freshness` commands exclude that tag, publish-conditions.yml's excludes nothing, and no generated
    notice table keeps a fct_sources_without_freshness row in seeds/dbt_project_evaluator_exceptions.csv.
    tests/test_dbt_notice_source_freshness_runs.py runs publish-conditions.yml's selection and finds all four red.
    """
    without, tagged, tables = set(), set(), set()
    for path, text in files.items():
        if path.name.endswith("__sources.yml"):
            for source in yaml.safe_load(text)["sources"]:
                for table in source["tables"]:
                    name = f"{source['name']}.{table['name']}"
                    config = table.get("config") or {}
                    tables.add(name)
                    if config.get("freshness") is None:
                        without.add(name)
                    if generator.PDF_NOTICE_TAG in (config.get("tags") or []):
                        tagged.add(name)
    pdfs = {f"{s.club}.{s.table}" for s in generator.notice_sources() if not s.hand_staged and generator.is_pdf_notice(s)}
    assert len(pdfs) >= 4, "the four PDF notices of 2026-10-09 are not all generated"
    assert without == set()
    assert tagged == pdfs
    excepted = {
        row["id_to_exclude"]
        for row in _seed("dbt_project_evaluator_exceptions")
        if row["fct_name"] == "fct_sources_without_freshness"
    }
    assert not tables & excepted, sorted(tables & excepted)

    exclude = f"--exclude tag:{generator.PDF_NOTICE_TAG}"
    workflows = PIPELINE.parent / ".github" / "workflows"
    ci = yaml.safe_load((workflows / "pipeline-tests.yml").read_text(encoding="utf-8"))["jobs"]["dbt"]["steps"]
    (ci_step,) = [step for step in ci if step.get("name") == "dbt source freshness"]
    assert ci_step["run"] == f"dbt source freshness --profiles-dir . {exclude}"
    test_sh = (PIPELINE.parent / "scripts" / "test.sh").read_text(encoding="utf-8")
    (local,) = re.findall(r'^\s*step "dbt source freshness"\s+(.*)$', test_sh, re.MULTILINE)
    assert local.endswith(f"source freshness --profiles-dir . {exclude}"), local
    conditions = yaml.safe_load((workflows / "publish-conditions.yml").read_text(encoding="utf-8"))
    (production,) = [
        step["run"]
        for job in conditions["jobs"].values()
        for step in job.get("steps") or []
        if 'dbt/bin/dbt" source freshness' in str(step.get("run", ""))
    ]
    assert "tag:notices_job" in production and "--exclude" not in production


def test_every_notice_raw_table_carries_elementarys_checks_and_each_dated_source_its_event_freshness(files):
    """Decision 102, through the generator so one edit reaches every source: each raw table carries
    make_dbt_staging.py's raw_table_checks() for its own cadence (freshness on the hourly and daily ones), and each
    staging model whose source states when it edited a notice carries event_freshness_check() on that date, the gap
    from the newest notice's own date to the build. A source with no such field gets none: its metric would be the
    same empty answer at every build."""
    notices = {s.table: s for s in generator.notice_sources() if not s.hand_staged}
    # A steward's areas layer sits in its club's notice files too (generate_notice_models.py's render_all()), with the
    # same raw-table checks, and dates no notice.
    sources = {**notices, **{s.table: s for s in generator.area_sources()}}
    fields = generator._fields_seed()
    dated = {s.stg_model for s in notices.values() if generator.dates_its_notices(s, fields)}
    tables = models = 0
    for path, text in files.items():
        if path.name.endswith("_notices__sources.yml"):
            for source in yaml.safe_load(text)["sources"]:
                for table in source["tables"]:
                    tables += 1
                    checks = [test for test in table["data_tests"] if next(iter(test)).startswith("elementary.")]
                    assert checks == make_dbt_staging.raw_table_checks(sources[table["name"]].cadence), table["name"]
        if path.name.endswith("_notices__models.yml"):
            for model in yaml.safe_load(text)["models"]:
                models += 1
                expected = [generator.event_freshness_check()] if model["name"] in dated else []
                assert [test for test in model.get("data_tests") or []] == expected, model["name"]
    assert tables == models == len(sources)
    assert len(dated) >= 219, "157 hourly and 62 daily sources at d5e97f8c"


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
    Every steward's areas layer's base model is a table as well, because its outlines are what each read parses
    (render_base()'s `area`).
    """
    sources = {source.key: source for source in generator.notice_sources() if not source.hand_staged}
    assert generator.TABLE_BASES <= set(sources), sorted(generator.TABLE_BASES - set(sources))
    assert all(sources[key].reader.spatial for key in generator.TABLE_BASES)
    tables = {
        path.stem
        for path, text in files.items()
        if path.name.startswith("base_") and path.suffix == ".sql" and "{{ config(materialized='table') }}" in text
    }
    areas = {source.base_model for source in generator.area_sources()}
    assert tables == {sources[key].base_model for key in generator.TABLE_BASES} | areas


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


def test_every_stewards_areas_layer_lands_in_the_warehouse_of_the_hourly_build_that_places_with_it():
    """The test above, for the layers seeds/notice_steward_areas.csv names: int_closures__club_notices places a point by
    its steward's own area in the hourly build, whose warehouse holds a conditions leg's tables and a notices leg's
    served copy, never the monthly store. An areas layer on the monthly lane would never be there, and every point it
    was named to place would keep its own, every hour, with every run green."""
    from extract._contract import all_resources, discover, discover_shared
    from extract._run import LEGS, leg_tables

    resources = all_resources(discover() + discover_shared())
    hourly = set().union(*(leg_tables(leg, resources) for leg in LEGS))
    areas = generator.area_sources()
    assert areas, "no steward's areas layer to check: FDEP's park boundaries were named on 2026-10-11"
    assert {source.table for source in areas} <= hourly, sorted({source.table for source in areas} - hourly)


def test_each_link_joins_a_notice_source_to_a_layer_of_its_own_stewards_areas():
    """The maintainer's answer to Q3 (poll of 2026-10-11): "a status point inside exactly one of its steward's own areas
    takes that area". So a row of seeds/notice_steward_areas.csv links a generated notice source with a geometry to a
    layer the same steward publishes (sources.json's `steward`, extracted by the same folder), never another
    organization's areas, and links a notice source to one layer only."""
    registry = generator._registry()
    notices = {source.key: source for source in generator.notice_sources() if not source.hand_staged}
    areas = {source.key: source for source in generator.area_sources()}
    rows = _seed("notice_steward_areas")
    assert rows, "the seed is empty: a rule with no row places nothing"
    assert len({row["source_key"] for row in rows}) == len(rows), "a notice source is linked to one areas layer"
    for row in rows:
        notice, area = notices.get(row["source_key"]), areas.get(row["areas_source_key"])
        assert notice is not None and notice.reader.spatial, f"{row['source_key']}: no generated notice source with a geometry"
        assert area is not None, f"{row['areas_source_key']}: not staged as a steward's areas layer"
        assert notice.club == area.club, f"{row['source_key']} and its areas are extracted by different folders"
        assert registry[row["source_key"]]["steward"] == registry[row["areas_source_key"]]["steward"], row
        assert row["why"].strip(), row


def test_a_stewards_areas_layer_is_staged_as_areas_and_never_as_notices(files):
    """It joins no notice union, part or readers seed, so the gate never reads a park boundary as a notice, and the
    areas union reads exactly the areas layers, each staged with its key, its own id and its outline and no fact a
    notice carries."""
    areas = generator.area_sources()
    staged = {source.stg_model for source in areas}
    assert not {row["source_key"] for row in _seed("notice_readers")} & {source.key for source in areas}
    assert set(re.findall(r"ref\('([a-z0-9_]+)'\)", files[generator.AREAS_UNION_MODEL])) == staged
    part = generator.UNION_MODEL.stem.removesuffix("_unioned") + "_part_"
    for path, text in files.items():
        if path.name.startswith(part):
            assert not set(re.findall(r"ref\('([a-z0-9_]+)'\)", text)) & staged, path.name
    for source in areas:
        stg = files[source.folder / f"{source.stg_model}.sql"]
        assert " as area_id," in stg and " as geom_geojson," in stg, source.stg_model
        assert " as title," not in stg and " as status," not in stg, source.stg_model


def test_a_link_to_a_layer_no_closures_or_warnings_file_declares_stops_the_generator(monkeypatch):
    """A layer a leg never reads could place nothing in the hourly build (the lane test above), so naming one stops
    the run rather than staging a source no build holds."""
    monkeypatch.setattr(generator, "area_layer_keys", lambda: {"no_such_layer"})
    with pytest.raises(SystemExit, match="no_such_layer"):
        generator.area_sources()


def test_with_no_link_the_areas_union_is_an_empty_relation_of_the_areas_columns():
    """int_closures__steward_areas always has a union to read, so removing the last seed row places nothing and fails
    nothing."""
    text = generator.render_areas_union([])
    assert text.rstrip().endswith("where false")
    for name, kind in generator.AREA_COLUMNS:
        assert f"cast(null as {kind}) as {name}" in text
