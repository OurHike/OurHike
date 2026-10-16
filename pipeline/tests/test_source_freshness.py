"""Every monthly source's dbt freshness reads the extract's run log, and both warns and errors.

The maintainer, 2026-10-15: freshness is measured from OurHike's own last successful read of a
source, read or confirmed unchanged, in every lane, and every freshness check
carries a warning and an error. tests/test_notice_source_freshness.py holds the
hourly and daily sources; this file holds, without
dbt, every source the monthly lane builds from:

- it measures from macros/last_read_or_confirmed_at.sql (make_dbt_staging.py's
  LOADED_AT_QUERY), never from `_loaded_at`, which a change check that finds a
  source unchanged leaves at its last load, and never from a date of the
  source's own;
- it warns after 35 days unread and errors after 62 (MONTHLY_FRESHNESS_DAYS),
  a reviewed file, a PDF's and a workbook's tables included;
- the Python steps' own tables are the one exception to the basis: no run log
  row names them, so they keep `_loaded_at`, which a step stamps in the build
  that reads it.

The YAML is read as dbt merges it: a table's own `config` over its source's.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import make_dbt_staging

STAGING = Path(__file__).resolve().parent.parent / "dbt" / "models" / "staging"
#: The tags publish-conditions.yml's freshness step selects the hourly lane's sources by
#: (generate_notice_models.py's NOTICES_JOB_TAG, and the conditions job's own).
HOURLY_TAGS = {"notices_job", "conditions_job"}
#: The cadences of the hourly lane (build_marts.py's FASTER_THAN_MONTHLY).
FASTER = {"hourly", "daily"}
#: The Python steps' tables (build_marts.py's DERIVED_SOURCE).
DERIVED = "derived"


def _tables() -> dict[tuple[str, str], dict]:
    """{(source, table): its effective config, with `path`}, over every sources block, the generated ones included."""
    found = {}
    for path in sorted(STAGING.rglob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for source in document.get("sources") or []:
            for table in source.get("tables") or []:
                config = {**(source.get("config") or {}), **(table.get("config") or {})}
                found[(source["name"], table["name"])] = {"path": path, **config}
    return found


def _monthly(config: dict) -> bool:
    """A table the monthly lane builds from: no faster cadence and neither hourly job's tag (an untagged cadence is
    monthly in effect, build_marts.py's docstring, "A LANE BUILDS ONLY ITS OWN NODES")."""
    cadence = (config.get("meta") or {}).get("cadence")
    return cadence not in FASTER and not HOURLY_TAGS & set(config.get("tags") or [])


@pytest.fixture(scope="module")
def tables() -> dict[tuple[str, str], dict]:
    return _tables()


def _thresholds(config: dict) -> tuple[dict | None, dict | None]:
    freshness = config.get("freshness") or {}
    return freshness.get("warn_after"), freshness.get("error_after")


EXPECTED = (
    {"count": make_dbt_staging.MONTHLY_FRESHNESS_DAYS[0], "period": "day"},
    {"count": make_dbt_staging.MONTHLY_FRESHNESS_DAYS[1], "period": "day"},
)


def test_the_monthly_pair_is_35_days_to_warn_and_62_to_error():
    """The lead's pick of two missed monthly refreshes, both @unvalidated (make_dbt_staging.py says what they do)."""
    assert make_dbt_staging.MONTHLY_FRESHNESS_DAYS == (35, 62)
    assert make_dbt_staging.LOADED_AT_QUERY == "{{ last_read_or_confirmed_at(this) }}"


def test_every_monthly_source_reads_the_run_log_and_warns_at_35_days_and_errors_at_62(tables):
    monthly = {key: config for key, config in tables.items() if _monthly(config) and key[0] != DERIVED}
    assert len(monthly) >= 470, "407 generated and 68 hand-written monthly tables at 3133c11a"
    problems = []
    for (source, table), config in sorted(monthly.items()):
        where = f"{config['path'].relative_to(STAGING)}: {source}.{table}"
        if "loaded_at_field" in config or config.get("loaded_at_query") != make_dbt_staging.LOADED_AT_QUERY:
            problems.append(f"{where} is measured by {config.get('loaded_at_field') or config.get('loaded_at_query')}")
        if _thresholds(config) != EXPECTED:
            problems.append(f"{where} warns and errors at {_thresholds(config)}")
    assert problems == []


def test_the_reviewed_files_and_the_tables_read_off_a_pdf_or_a_workbook_are_measured_too(tables):
    """Each carried `freshness: null` or none at all: a reviewed file's `_loaded_at` moves only when its bytes do, and
    the fixture warehouse never holds a PDF's or a workbook's table, which a query of `_loaded_at` failed on. The run
    log records a reviewed file confirmed unchanged as `skipped` and never reads the table, so neither reason holds."""
    for key in (
        ("registry", "raw_registry__sources"),
        ("podcasts", "raw_podcasts__podcast_episodes"),
        ("atc", "raw_atc__water_distance"),
        ("census", "raw_census__census_tiger_states"),
        ("gatc", "raw_gatc__gatc_water_sources"),
        ("ata", "raw_ata__ata_water_cache_boxes"),
        ("wmc", "raw_wmc__wmc_hike_ratings"),
    ):
        assert _thresholds(tables[key]) == EXPECTED, key
    assert not [key for key, config in tables.items() if "freshness" in config and config["freshness"] is None]


def test_the_python_steps_tables_keep_their_own_stamp_with_the_monthly_pair(tables):
    """No run log row names a derived table, so last_read_or_confirmed_at() would fall back to the log's newest row
    and measure nothing of it; a step stamps `_loaded_at` itself, in the build that reads the table."""
    derived = {key: config for key, config in tables.items() if key[0] == DERIVED}
    assert len(derived) >= 10
    for key, config in derived.items():
        assert (config.get("loaded_at_field"), "loaded_at_query" in config) == ("_loaded_at", False), key
        assert _thresholds(config) == EXPECTED, key
