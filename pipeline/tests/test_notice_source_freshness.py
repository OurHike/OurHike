"""Every notice source's dbt freshness reads the extract's run log, and errors once it has gone unread too long.

Decision 100 (the maintainer's poll of 2026-10-07): a notice source refused
by its host is a warning on the extract run, and dbt's source freshness turns
it red once it has gone 24 hours without being read or confirmed unchanged.
tests/test_dbt_notice_source_freshness_runs.py runs dbt on that rule; this
file holds, without dbt, that every source the rule covers carries it:

- every generated notice source (generate_notice_models.py) and every one of
  the conditions job's own upstreams that a leg can refuse on its own
  measures from macros/last_read_or_confirmed_at.sql, never from
  `_loaded_at`, which a FRESH check leaves at its last load;
- each errors after FRESHNESS_HOURS for its cadence, and a source whose
  sources.json row says reaches_hikers false only warns, as
  extract/_run.py's quiet_refusals() keeps its refusal from failing the run;
- each is tagged with the job whose run log measures it, which is how
  publish-conditions.yml's freshness step selects them.

The YAML is read as dbt merges it: a table's own `config` over its source's.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import generate_notice_models as generator
from extract._contract import all_resources, discover, discover_shared
from extract._run import DUE_AFTER, HOURLY_JOB_TABLES, LEGS, NOTICES_JOB, leg_tables, stops_the_leg

STAGING = Path(__file__).resolve().parent.parent / "dbt" / "models" / "staging"
MEASURE = "{{ last_read_or_confirmed_at(this) }}"


def _tables() -> dict[str, dict]:
    """{raw table: its effective source config}, over every sources block under models/staging, generated included."""
    found = {}
    for path in sorted(STAGING.rglob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for source in document.get("sources") or []:
            for table in source.get("tables") or []:
                config = {**(source.get("config") or {}), **(table.get("config") or {})}
                found[table["name"]] = {"source": source["name"], "path": path, **config}
    return found


def _hours(threshold: dict | None) -> float | None:
    if threshold is None:
        return None
    return threshold["count"] * {"hour": 1, "day": 24}[threshold["period"]]


def _thresholds(config: dict) -> tuple[float | None, float | None]:
    freshness = config.get("freshness") or {}
    return _hours(freshness.get("warn_after")), _hours(freshness.get("error_after"))


@pytest.fixture(scope="module")
def tables() -> dict[str, dict]:
    return _tables()


@pytest.fixture(scope="module")
def resources():
    return all_resources(discover() + discover_shared())


def test_a_daily_sources_thresholds_are_the_hourly_ones_plus_the_day_it_waits_to_be_due():
    """extract/_run.py's due() checks a daily resource only once its last good check is DUE_AFTER old, so the hours a
    healthy one goes unread by design are added to the hourly sources' thresholds, never counted against it."""
    day = DUE_AFTER["daily"].total_seconds() / 3600
    assert generator.FRESHNESS_HOURS["daily"] == tuple(hours + day for hours in generator.FRESHNESS_HOURS["hourly"])
    assert generator.FRESHNESS_HOURS["hourly"][1] == 24, "decision 100's 24 hours"


def test_nws_alerts_are_red_after_2_hours_unread_and_warn_after_1():
    """Decision 101 (the maintainer's poll of 2026-10-07: "Both, NWS red after 2 h"): with the hourly runs an hour
    apart, one refused read warns and two in a row are red; the warning is half the error, as FRESHNESS_HOURS has it."""
    assert generator.NWS_FRESHNESS_HOURS == (1, 2)


def test_every_generated_notice_source_measures_from_the_run_log_by_its_cadence(tables):
    problems = []
    for source in generator.notice_sources():
        if source.hand_staged:
            continue
        config = tables[source.table]
        if "loaded_at_field" in config or config.get("loaded_at_query") != MEASURE:
            problems.append(f"{source.table}: measured by {config.get('loaded_at_field') or config.get('loaded_at_query')}")
        warn, error = _thresholds(config)
        # A PDF notice included: CI's freshness leaves it out by its tag, never by dropping its thresholds
        # (tests/test_generated_notice_models.py).
        if source.cadence == "monthly":
            expected = (7 * 24, None)
        else:
            hours = generator.FRESHNESS_HOURS[source.cadence]
            quiet = (source.entry or {}).get("reaches_hikers") is False
            expected = (hours[0], None if quiet else hours[1])
        if (warn, error) != expected:
            problems.append(f"{source.table} ({source.cadence}): warns at {warn} h and errors at {error} h, not {expected}")
    assert problems == []


def test_only_the_notices_jobs_tables_are_tagged_for_its_run_log(tables, resources):
    """publish-conditions.yml selects `tag:notices_job` only when it read a notices copy, whose run log is the one
    these are measured from; a table the notices legs do not read would be measured from no row at all."""
    notices = set().union(*(leg_tables(name, resources) for name, leg in LEGS.items() if leg.job == NOTICES_JOB))
    tagged = {table for table, config in tables.items() if "notices_job" in (config.get("tags") or [])}
    generated = {source.table for source in generator.notice_sources() if not source.hand_staged}
    assert tagged <= generated, sorted(tagged - generated)
    assert tagged == generated & notices, sorted(tagged ^ (generated & notices))


def test_every_conditions_job_upstream_a_leg_can_refuse_on_its_own_errors_after_24_hours_unread_and_nws_after_2(
    tables, resources
):
    """The hourly run's extract refusal is a warning since decision 101 (the maintainer's poll of 2026-10-07: "Both,
    NWS red after 2 h"), for these as for the notices job's sources under decision 100, so each carries the red in
    freshness: 24 hours unread, NWS's alerts 2 (NWS_FRESHNESS_HOURS). OurHike's own Postgres rows are not among them:
    a failed read of those stops the whole leg (extract/_run.py's stops_the_leg()), which is red at once."""
    by_table = {resource.table: resource for resource in resources}
    refusable = {table for table in HOURLY_JOB_TABLES if not stops_the_leg(by_table[table])}
    assert len(refusable) == 8, sorted(refusable)
    tagged = {table for table, config in tables.items() if "conditions_job" in (config.get("tags") or [])}
    assert tagged == refusable, sorted(tagged ^ refusable)
    problems = []
    for table in sorted(refusable):
        config = tables[table]
        if config.get("loaded_at_query") != MEASURE:
            problems.append(f"{table}: measured by {config.get('loaded_at_query') or config.get('loaded_at_field')}")
        expected = generator.FRESHNESS_HOURS[by_table[table].cadence]
        if table == "raw_nws__alerts":
            expected = generator.NWS_FRESHNESS_HOURS
        if _thresholds(config) != expected:
            problems.append(f"{table}: warns and errors at {_thresholds(config)} h, not {expected}")
    assert problems == []
