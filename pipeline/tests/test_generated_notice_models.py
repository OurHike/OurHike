"""The club notice sources' generated dbt models are what pipeline/generate_notice_models.py writes (decision 53, phase C).

The generator's output is committed, so a reviewer reads the SQL that runs.
This holds the two together: a file on disk that differs from what the
generator writes now, a file it would write that is missing, or a file it no
longer writes fails here, with the command that fixes it. So a closures or
warnings resource registered in a club folder without re-running the
generator fails the pipeline suite rather than staying unstaged, and a
generated file edited by hand is caught.

It also holds what the generated models rest on and the generator cannot
check by itself: every field the ArcGIS seed names is a field the layer's
measured field list holds; every hand-staged notice table is one the closures
family reads; no pub_ writer reads a club notice model except through the
marts; and a source that ships has an exactness test that fails the build.
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
    assert not problems, "run `python generate_notice_models.py` from pipeline/:\n" + "\n".join(problems)


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
            if row[role]:
                assert row[role] in measured, f"{key}: {role} names {row[role]!r}, which the layer's field list does not hold"


def test_every_status_value_belongs_to_a_source_whose_seed_row_names_a_status_field():
    fields = {row["source_key"]: row for row in _seed("notice_source_fields")}
    readers = {source.key: source.reader for source in generator.notice_sources() if not source.hand_staged}
    for row in _seed("notice_status_values"):
        key = row["source_key"]
        has_status = bool(fields.get(key, {}).get("status")) or "status" in readers[key].roles
        assert has_status, f"{key}: a status value for a source whose status field is not staged"


def test_a_shipping_source_has_an_exactness_test_that_fails_the_build(files):
    """A held source warns, so one bad table cannot stop every club's closures; a shipping one must fail loudly."""
    registry = generator._registry()
    for path, text in files.items():
        if not path.name.endswith("__sources.yml"):
            continue
        for source in yaml.safe_load(text)["sources"]:
            for table in source["tables"]:
                key = re.search(r"sources\.json `([^`]+)`", table["description"]).group(1)
                (test,) = [t["duplicates_are_exact"] for t in table["data_tests"]]
                ships = registry.get(key, {}).get("reaches_hikers") is True
                assert test["config"]["severity"] == ("error" if ships else "warn"), key


def test_no_pub_writer_reads_a_club_notice_model_except_through_the_marts():
    """int_warnings__wording_leaks reads the finals, so a writer that read a club notice model directly would go unchecked."""
    generated = {source.stg_model for source in generator.notice_sources() if not source.hand_staged}
    generated |= {source.base_model for source in generator.notice_sources() if not source.hand_staged}
    generated |= {"int_closures__club_notices", "int_closures__club_notices_unioned", "int_closures__window_carried"}
    for path in (DBT / "models" / "publish").glob("pub_*.sql"):
        refs = set(re.findall(r"ref\('([a-z0-9_]+)'", path.read_text()))
        assert not refs & generated, f"{path.name} reads {sorted(refs & generated)}"


def test_the_readers_seed_marks_every_feed_a_window():
    for row in _seed("notice_readers"):
        assert (row["listing"] == "window") == (row["reader"] == "feed_notices"), row["raw_table"]


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
