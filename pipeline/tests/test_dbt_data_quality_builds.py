"""The data-quality page's two files, built by dbt from Elementary-shaped tables (step 4).

The warehouse here holds what pub_data_quality and pub_conditions_data_quality
read, in the shapes Elementary 0.26.0 writes them on dbt 2.0.6 and DuckDB
(read off a scratch project's tables, 2026-10-08, macros/data_quality.sql's
header): three builds of one lane's history, each check of the third (this
build) chosen to reach one rule of the file, and a project graph in which two
raw tables publish, three are held, one is OurHike's own registry, and one is
a step's derived table; and this build's `dbt source freshness` results, as
Elementary's end-of-run hook writes them. Then the two writers
are built, with Elementary on,
and each file is read field by field: what counts, what is named, the order of
what needs a look, since when, which series are charted, their window and
their cap, the bands an earlier build's kept run gives them (row_history.py's
"THE BANDS"), the learning count, and that no row value, sample, coordinate,
check message or held table's name reaches either. A second warehouse holds no
result at all.

Run by the dbt job, which sets OURHIKE_DBT, as the other *_builds.py files are;
the pytest job, which has no dbt, skips.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

import row_history

PIPELINE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = PIPELINE_DIR / "dbt"
DBT = os.environ.get("OURHIKE_DBT")
pytestmark = pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")

#: This build's start (build_marts.py's OURHIKE_BUILD_STARTED_AT), and the two builds before it in the history.
STARTED = "2026-10-08 07:00:00"
B1, B2, B3 = "2026-10-06 07:05:00", "2026-10-07 07:05:00", "2026-10-08 07:05:00"
#: Planted wherever a check's own words, a sample or a row's value could hide; none may reach either file.
SECRETS = (
    "SECRET-DESCRIPTION",
    "41.0123",
    "-74.5678",
    "SECRET-OTHER",
    "SECRET-RESULT-ROWS",
    "SECRET-PARAM",
    "SECRET-ANOMALY",
    "SECRET-CLUB",
    "SECRET-VALUE",
    "SECRET-SOURCE-VALUE",
    # A column's minimum, one row's own value.
    "0.1234",
)
#: The tables and tests a held source reaches: never named.
HELD_NAMES = (
    "raw_secret__secret_layer",
    "stg_secret__layer",
    "int_trail_lines__unioned",
    "int_trail_lines__history",
    "raw_mystery__mystery_layer",
    "stg_club__notices",
    "raw_club__club_news",
    "stg_derived__osm_water",
    "assert_unioned_rows",
    "ghost_test",
)

DEC = "source.ourhike.dec.raw_nysdec__dec_hiking_trails"
SECRET = "source.ourhike.secret.raw_secret__secret_layer"
MYSTERY = "source.ourhike.mystery.raw_mystery__mystery_layer"
REGISTRY = "source.ourhike.registry.raw_registry__sources"
NWS = "source.ourhike.nws.raw_nws__alerts"
ATC_CHALLENGES = "source.ourhike.atc.raw_atc__challenges_atc"
OPRHP = "source.ourhike.oprhp.raw_nysparks__oprhp_trail_closures"
CLUB = "source.ourhike.club.raw_club__club_news"
DERIVED = "source.ourhike.derived.osm_water"
SOURCES = {
    DEC: ("dec", "raw_nysdec__dec_hiking_trails"),
    SECRET: ("secret", "raw_secret__secret_layer"),
    MYSTERY: ("mystery", "raw_mystery__mystery_layer"),
    REGISTRY: ("registry", "raw_registry__sources"),
    NWS: ("nws", "raw_nws__alerts"),
    ATC_CHALLENGES: ("atc", "raw_atc__challenges_atc"),
    OPRHP: ("oprhp", "raw_nysparks__oprhp_trail_closures"),
    CLUB: ("club", "raw_club__club_news"),
    DERIVED: ("derived", "osm_water"),
}
# int_sources__publication's rows. club_news publishes by name, but the club's notice_readers row names its key
# club_notices, which is held, and that row wins. osm_water publishes, and derived.osm_water is a step's table
# that only shares its name.
PUBLICATION = [
    ("dec_hiking_trails", True),
    ("secret_layer", False),
    ("nws_alerts", True),
    ("reference/challenges/atc", True),
    ("oprhp_trail_closures", True),
    ("club_news", True),
    ("club_notices", False),
    ("osm_water", True),
]
NOTICE_READERS = [("club_notices", "raw_club__club_news")]
#: The rule 23 (the maintainer's poll, 2026-10-15): each published source's last post, its own layer's
#: newest edit date, as int_sources__final and int_sources__data_edited give it. secret_layer is held, so its title
#: and day never reach the file; osm_water publishes and its layer states no date, so it has no entry.
FINAL_SOURCES = [
    ("dec_hiking_trails", "DEC hiking trails", True),
    ("oprhp_trail_closures", "OPRHP temporary trail closures", True),
    ("secret_layer", "SECRET-HELD-TITLE", False),
    ("osm_water", "OSM water", True),
]
DATA_EDITED = [("dec_hiking_trails", "2026-09-18"), ("oprhp_trail_closures", "2026-10-07"), ("secret_layer", "2001-01-01")]

MART = "model.ourhike.trail_lines.v1"
# A second mart, whose table check warns on both of its metrics.
CLOSURES = "model.ourhike.closures.v1"
UNION = "model.ourhike.int_trail_lines__unioned"
AFTER = "model.ourhike.int_trail_lines__after_the_mart"
CHECKED = "model.ourhike.int_trail_lines__checked"
MODELS = {
    "model.ourhike.stg_dec__hiking_trails": ("models/staging/dec/stg_dec__hiking_trails.sql", [DEC]),
    "model.ourhike.stg_secret__layer": ("models/staging/secret/stg_secret__layer.sql", [SECRET]),
    "model.ourhike.stg_registry__sources": ("models/staging/registry/stg_registry__sources.sql", [REGISTRY]),
    "model.ourhike.stg_nws__alerts": ("models/staging/nws/stg_nws__alerts.sql", [NWS]),
    "model.ourhike.stg_atc__challenges": ("models/staging/atc/stg_atc__challenges.sql", [ATC_CHALLENGES]),
    "model.ourhike.stg_club__notices": ("models/staging/club/stg_club__notices.sql", [CLUB]),
    "model.ourhike.stg_derived__osm_water": ("models/staging/derived/stg_derived__osm_water.sql", [DERIVED]),
    UNION: (
        "models/intermediate/trail_lines/int_trail_lines__unioned.sql",
        ["model.ourhike.stg_dec__hiking_trails", "model.ourhike.stg_secret__layer"],
    ),
    CHECKED: (
        "models/intermediate/trail_lines/int_trail_lines__checked.sql",
        ["model.ourhike.stg_dec__hiking_trails", "model.ourhike.stg_registry__sources"],
    ),
    MART: ("models/marts/trail_lines/trail_lines.sql", [UNION]),
    CLOSURES: ("models/marts/closures/closures.sql", ["model.ourhike.stg_nws__alerts"]),
    AFTER: ("models/intermediate/trail_lines/int_trail_lines__after_the_mart.sql", [MART]),
    "model.ourhike.pub_trails_geojson": ("models/publish/pub_trails_geojson.sql", [MART]),
}
SNAPSHOTS = {"snapshot.ourhike.int_trail_lines__history": ("snapshots/trail_lines/int_trail_lines__history.sql", [UNION])}

# Each test: (unique id, short name, parent, depends on, path). None for the parent of a singular test.
YML = "models/marts/trail_lines/_trail_lines__models.yml"
TESTS = {
    "not_null_dec_name": ("not_null", "model.ourhike.stg_dec__hiking_trails", None, "models/staging/dec/_dec__models.yml"),
    "unique_secret_id": ("unique", "model.ourhike.stg_secret__layer", None, "models/staging/secret/_secret__models.yml"),
    "not_null_mart_name": ("not_null", MART, None, YML),
    "accepted_values_mart_status": ("accepted_values", MART, None, YML),
    "expression_is_true_union": ("expression_is_true", UNION, None, "models/intermediate/trail_lines/_x.yml"),
    "relationships_after_id": ("relationships", AFTER, [AFTER, MART], "models/intermediate/trail_lines/_x.yml"),
    "assert_trail_lines_are_lines": (
        "assert_trail_lines_are_lines",
        None,
        [MART],
        "tests/trail_lines/assert_trail_lines_are_lines.sql",
    ),
    # Reads two tables and was given no one parent, so Elementary's result names no table.
    "assert_lines_match_checks": (
        "assert_lines_match_checks",
        None,
        [MART, CHECKED],
        "tests/trail_lines/assert_lines_match_checks.sql",
    ),
    "assert_unioned_rows": ("assert_unioned_rows", None, [UNION], "tests/singular/assert_unioned_rows.sql"),
    "volume_dec": ("volume_anomalies", DEC, None, "models/staging/dec/_dec__sources.yml"),
    "volume_secret": ("volume_anomalies", SECRET, None, "models/staging/secret/_secret__sources.yml"),
    "volume_mart": ("volume_anomalies", MART, None, YML),
    "table_closures": ("table_anomalies", CLOSURES, None, "models/marts/closures/_closures__models.yml"),
    "freshness_nws": ("freshness_anomalies", NWS, None, "models/staging/nws/_nws__sources.yml"),
    "schema_dec": ("schema_changes", DEC, None, "models/staging/dec/_dec__sources.yml"),
    "schema_mystery": ("schema_changes", MYSTERY, None, "models/staging/mystery/_mystery__sources.yml"),
    "columns_mart": ("column_anomalies", MART, None, YML),
    "dimension_mart": ("dimension_anomalies", MART, None, YML),
    "exposure_schema_mart": ("exposure_schema_validity", MART, None, YML),
    "not_null_dec_id": ("not_null", "model.ourhike.stg_dec__hiking_trails", None, "models/staging/dec/_dec__models.yml"),
    "unique_dec_key": ("unique", "model.ourhike.stg_dec__hiking_trails", None, "models/staging/dec/_dec__models.yml"),
    "accepted_values_seed": ("accepted_values", "seed.ourhike.poi_types", None, "seeds/_seeds.yml"),
    "not_null_nws_id": ("not_null", "model.ourhike.stg_nws__alerts", None, "models/staging/nws/_nws__models.yml"),
    "not_null_challenges_id": ("not_null", "model.ourhike.stg_atc__challenges", None, "models/staging/atc/_atc__models.yml"),
    "not_null_club_id": ("not_null", "model.ourhike.stg_club__notices", None, "models/staging/club/_club__models.yml"),
    "not_null_osm_id": ("not_null", "model.ourhike.stg_derived__osm_water", None, "models/staging/derived/_derived__models.yml"),
    "not_null_checked_id": ("not_null", CHECKED, None, "models/intermediate/trail_lines/_x.yml"),
    "unique_history_id": ("unique", "snapshot.ourhike.int_trail_lines__history", None, "snapshots/trail_lines/_x.yml"),
    "not_null_writer_document": ("not_null", "model.ourhike.pub_trails_geojson", None, "models/publish/_x.yml"),
}
#: Each test's error_if and meta in Elementary's dbt_tests, where one is not dbt_project.yml's `>0` and `{}` (decision
#: 204): a warning past its error_if is failed on the page, unless it stays at warn, and a level is no count of rows.
THRESHOLDS = {
    # Warned 6 at zero tolerance, kept a warning by its meta, as the four closures key tests are.
    "assert_lines_match_checks": (">0", {"stays_at_warn": "decision 197"}),
    # A level (macros/test_levels.sql): warned at 1, an error only at 2, and never a count.
    "not_null_challenges_id": (">1", {"scores_a_level": True}),
}


def _uid(name: str) -> str:
    return f"test.ourhike.{name}"


def _hours_before(at: str, hours: int) -> str:
    return (datetime.fromisoformat(at) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def _table_of(parent: str | None) -> tuple[str | None, str | None]:
    """The (schema, table) Elementary names a test's parent by."""
    if parent is None:
        return "dbt_test__audit", None
    if parent in SOURCES:
        return "raw", SOURCES[parent][1]
    if parent.startswith("seed."):
        return "seeds", parent.rsplit(".", 1)[-1]
    schema = {"models/marts/": "marts", "models/publish/": "publish", "models/staging/": "staging"}
    path = (MODELS.get(parent) or SNAPSHOTS.get(parent))[0]
    # A versioned model's relation is named with its version, as the project's marts are (trail_lines_v1).
    parts = parent.split(".")
    name = "_".join(parts[2:])
    return next((value for key, value in schema.items() if path.startswith(key)), "intermediate"), name


def _result(
    name: str,
    *,
    invocation: str,
    at: str,
    status: str,
    test_type: str = "dbt_test",
    sub_type: str = "generic",
    column: str | None = None,
    failures: int | None = 0,
    result_id: str | None = None,
    schema_table: tuple[str, str] | None = None,
) -> dict:
    short, parent, _, _ = TESTS[name] if name in TESTS else ("ghost_test", "model.ourhike.stg_dec__hiking_trails", None, "")
    schema, table = schema_table or _table_of(parent)
    return {
        "id": result_id or f"{invocation}.{_uid(name)}.{column}.{sub_type}",
        "test_unique_id": _uid(name),
        "model_unique_id": parent,
        "invocation_id": invocation,
        "detected_at": at,
        "created_at": at,
        "database_name": "warehouse",
        "schema_name": schema,
        "table_name": table,
        "column_name": column,
        "test_type": test_type,
        "test_sub_type": sub_type,
        "test_short_name": short,
        "status": status,
        "failures": failures,
        # What a check says of its rows, and what a sample holds, are never read.
        "test_results_description": "SECRET-DESCRIPTION near 41.0123,-74.5678",
        "other": "SECRET-OTHER",
        "result_rows": '[{"name": "SECRET-RESULT-ROWS"}]',
        "test_params": json.dumps({"days_back": 14, "where_expression": "SECRET-PARAM"}),
    }


def _anomaly_row(
    result_id: str,
    bucket: str,
    value: float,
    low: float | None,
    high: float | None,
    anomalous: bool,
    at: str | None = None,
    **extra,
):
    """A scored bucket as a run stores it; `at` is when the run stored it, which is the bucket's own time unless said."""
    return {
        "elementary_test_results_id": result_id,
        "test_type": "anomaly_detection",
        "created_at": at or bucket,
        "detected_at": at or bucket,
        "row_index": 0,
        "result_row": json.dumps(
            {
                "bucket_end": bucket.replace(" ", "T"),
                "metric_value": value,
                "min_metric_value": low,
                "max_metric_value": high,
                "is_anomalous": anomalous,
                "metric_name": extra.get("metric", "row_count"),
                "column_name": extra.get("column"),
                "dimension": extra.get("dimension"),
                "dimension_value": extra.get("dimension_value"),
                "anomaly_description": "SECRET-ANOMALY",
                "anomalous_value": "SECRET-VALUE",
                "training_set_size": 2,
            }
        ),
    }


def _kept_band(result_id: str, bucket: str, low: float, high: float, at: str) -> dict:
    """A scored bucket as row_history.py restores it from an earlier build: its band fields alone (BAND_FIELDS)."""
    band = {"metric_name": "row_count", "column_name": None, "bucket_end": bucket.replace(" ", "T")}
    band |= {"min_metric_value": low, "max_metric_value": high}
    assert tuple(band) == row_history.BAND_FIELDS
    return {
        "elementary_test_results_id": result_id,
        "test_type": "anomaly_detection",
        "created_at": at,
        "detected_at": at,
        "row_index": 1,
        "result_row": json.dumps(band),
    }


#: When this build's freshness run measured, a minute after its checks, as build_marts.py runs it.
MEASURED = "2026-10-08 07:06:00"
#: A source's limits as Elementary stores them, JSON, and a monthly source's (make_dbt_staging.MONTHLY_FRESHNESS_DAYS).
NO_LIMIT = json.dumps({"count": None, "period": None})
MONTHLY_LIMITS = (json.dumps({"count": 35, "period": "day"}), json.dumps({"count": 62, "period": "day"}))
HOURLY_LIMITS = (json.dumps({"count": 12, "period": "hour"}), json.dumps({"count": 24, "period": "hour"}))


def _freshness(uid: str, status: str, seconds: int | None, limits: tuple[str, str], at: str = MEASURED) -> dict:
    """A row of dbt_source_freshness_results as Elementary 0.26.0's hook writes it on dbt 2.0.6 (measured 2026-10-15,
    build_marts.py's docstring, "EACH SOURCE'S FRESHNESS IS MEASURED FOR THE DATA-QUALITY FILE"): dbt's status
    capitalised, the read and the measure as ISO text, the limits as JSON, and max_loaded_at_time_ago_in_s null,
    which the hook leaves so. `seconds` is how long before the measure the extract last read the source; None for a
    runtime error, which carries no instant and no limit."""
    measured = datetime.fromisoformat(at)
    read = None if seconds is None else (measured - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "source_freshness_execution_id": f"{at}.{uid}",
        "unique_id": uid,
        "max_loaded_at": read,
        "snapshotted_at": None if seconds is None else measured.strftime("%Y-%m-%dT%H:%M:%S.123456Z"),
        "generated_at": at,
        "created_at": at,
        "max_loaded_at_time_ago_in_s": None,
        "status": status,
        "error": "SECRET-DESCRIPTION" if seconds is None else None,
        "invocation_id": f"freshness-{at}",
        "warn_after": None if seconds is None else limits[0],
        "error_after": None if seconds is None else limits[1],
    }


#: This build's freshness run and what came before it. Counted: dec's last result (it was measured twice in this
#: build), NWS's error (2 hours to error), the registry's warning (OurHike's own source, cleared), ATC's
#: challenges' warning with no error limit, as a reaches_hikers false source has, and OPRHP's runtime
#: error. Not counted: the build before's result, the held secret layer's, and a source Elementary's dbt_sources does
#: not describe.
FRESHNESS = [
    _freshness(DEC, "Warn", 40 * 86400, MONTHLY_LIMITS, at="2026-10-08 07:05:30"),
    _freshness(DEC, "Pass", 3 * 3600, MONTHLY_LIMITS),
    _freshness(DEC, "Error", 70 * 86400, MONTHLY_LIMITS, at=B2),
    _freshness(NWS, "Error", 11250, (json.dumps({"count": 1, "period": "hour"}), json.dumps({"count": 2, "period": "hour"}))),
    _freshness(REGISTRY, "Warn", 40 * 86400, MONTHLY_LIMITS),
    _freshness(ATC_CHALLENGES, "Warn", 13 * 3600, (HOURLY_LIMITS[0], NO_LIMIT)),
    _freshness(OPRHP, "runtime error", None, HOURLY_LIMITS),
    _freshness(SECRET, "Error", 90 * 86400, MONTHLY_LIMITS),
    _freshness("source.ourhike.ghost.raw_ghost__layer", "Warn", 50 * 86400, MONTHLY_LIMITS),
]


def _history() -> tuple[list[dict], list[dict], list[dict]]:
    """Every result, scored bucket and metric the lane's history holds: builds 1 and 2, then this one."""
    results, rows, metrics = [], [], []
    for invocation, at in (("b1-checks", B1), ("b2-checks", B2)):
        # Build 1 passed the dec volume check; build 2 warned on it, so its run of warnings began then.
        status = "pass" if invocation == "b1-checks" else "warn"
        volume = _result(
            "volume_dec",
            invocation=invocation,
            at=at,
            status=status,
            test_type="anomaly_detection",
            sub_type="row_count",
            failures=0 if status == "pass" else 1,
        )
        results.append(volume)
        if invocation == "b2-checks":
            rows.append(_anomaly_row(volume["id"], B2, 5262.0, 5100.0, 5400.0, True))
        results.append(_result("schema_dec", invocation=invocation, at=at, status="pass", test_type="schema_change"))
        results.append(_result("not_null_mart_name", invocation=f"{invocation}-stage-a", at=at, status="pass", column="name"))
        results.append(
            _result(
                "volume_secret", invocation=invocation, at=at, status="warn", test_type="anomaly_detection", sub_type="row_count"
            )
        )
        # The closures mart's one table check, two metrics, passing; build 2's run scored its bucket on each.
        for metric, value, low, high in (("row_count", 55.0, 50.0, 60.0), ("freshness", 3600.0, 0.0, 86400.0)):
            passed = _result(
                "table_closures", invocation=invocation, at=at, status="pass", test_type="anomaly_detection", sub_type=metric
            )
            results.append(passed)
            if invocation == "b2-checks":
                rows.append(_anomaly_row(passed["id"], B2, value, low, high, False, metric=metric))
    # The trail_lines mart's check ran in build 2 too, and row_history.py kept two of that run's bands, its fields alone:
    # one for the oldest hour this build's series keeps, which this build's run did not score, and one for an hour
    # both runs scored, where this build's newer band wins.
    earlier = _result(
        "volume_mart", invocation="b2-checks", at=B2, status="pass", test_type="anomaly_detection", sub_type="row_count"
    )
    results.append(earlier)
    rows += [
        _kept_band(earlier["id"], _hours_before(B3, 167), 1100.0, 1300.0, at=B2),
        _kept_band(earlier["id"], _hours_before(B3, 30), 980.0, 1020.0, at=B2),
    ]

    # This build: stage A, a retry of one of its tests, and the checks' pass.
    a, retry, checks = "b3-stage-a", "b3-retry", "b3-checks"
    t = "2026-10-08 07:01:00"
    results += [
        _result("not_null_dec_name", invocation=a, at=t, status="pass"),
        _result("unique_secret_id", invocation=a, at=t, status="warn", failures=3),
        _result("not_null_mart_name", invocation=a, at=t, status="warn", column="name", failures=5),
        _result("accepted_values_mart_status", invocation=a, at=t, status="fail", column="status", failures=2),
        _result("expression_is_true_union", invocation=a, at=t, status="error", failures=None),
        _result("relationships_after_id", invocation=a, at=t, status="error", column="id", failures=None),
        _result("assert_trail_lines_are_lines", invocation=a, at=t, status="pass"),
        _result("assert_lines_match_checks", invocation=a, at=t, status="warn", failures=6),
        _result("assert_unioned_rows", invocation=a, at=t, status="warn", failures=4),
        _result("not_null_dec_id", invocation=a, at=t, status="skipped", failures=None),
        _result("accepted_values_seed", invocation=a, at=t, status="pass"),
        _result("not_null_nws_id", invocation=a, at=t, status="pass"),
        _result("not_null_challenges_id", invocation=a, at=t, status="warn", column="id", failures=1),
        _result("not_null_club_id", invocation=a, at=t, status="warn", failures=1),
        _result("not_null_osm_id", invocation=a, at=t, status="warn", failures=1),
        _result("not_null_checked_id", invocation=a, at=t, status="pass"),
        _result("unique_history_id", invocation=a, at=t, status="pass"),
        _result("not_null_writer_document", invocation=a, at=t, status="pass"),
        _result("ghost", invocation=a, at=t, status="warn", failures=9),
        # Failed in stage A and passed on the retry: the retry's result counts.
        {**_result("unique_dec_key", invocation=a, at=t, status="fail", failures=2), "created_at": "2026-10-08 07:01:30"},
        {**_result("unique_dec_key", invocation=retry, at=t, status="pass"), "created_at": "2026-10-08 07:02:30"},
    ]
    volume = _result(
        "volume_dec", invocation=checks, at=B3, status="warn", test_type="anomaly_detection", sub_type="row_count", failures=1
    )
    secret = _result(
        "volume_secret", invocation=checks, at=B3, status="warn", test_type="anomaly_detection", sub_type="row_count", failures=1
    )
    # The trail_lines mart's row count, inside its band: in no needs_a_look entry, charted as every mart's is.
    mart_volume = _result(
        "volume_mart", invocation=checks, at=B3, status="pass", test_type="anomaly_detection", sub_type="row_count"
    )
    # The closures mart's table check warns on both its metrics: its row count counts, and its freshness, a metric
    # Elementary learns, counts nowhere (macros/data_quality.sql's header, "FRESHNESS").
    closures_rows, closures_fresh = (
        _result(
            "table_closures", invocation=checks, at=B3, status="warn", test_type="anomaly_detection", sub_type=metric, failures=1
        )
        for metric in ("row_count", "freshness")
    )
    null_count = _result(
        "columns_mart",
        invocation=checks,
        at=B3,
        status="warn",
        test_type="anomaly_detection",
        sub_type="null_count",
        column="name",
    )
    smallest = _result(
        "columns_mart",
        invocation=checks,
        at=B3,
        status="warn",
        test_type="anomaly_detection",
        sub_type="min",
        column="distance_ft",
    )
    # A second column's null count, the same metric as name's, and its null rate: three column series on one table.
    status_nulls, status_rate = (
        _result(
            "columns_mart",
            invocation=checks,
            at=B3,
            status="warn",
            test_type="anomaly_detection",
            sub_type=metric,
            column="status",
        )
        for metric in ("null_count", "null_percent")
    )
    dimension = _result(
        "dimension_mart", invocation=checks, at=B3, status="warn", test_type="anomaly_detection", sub_type="dimension", failures=3
    )
    # Elementary names a schema change's table in capitals.
    capitals = ("RAW", "RAW_NYSDEC__DEC_HIKING_TRAILS")
    results += [
        volume,
        secret,
        mart_volume,
        closures_rows,
        closures_fresh,
        null_count,
        smallest,
        status_nulls,
        status_rate,
        _result(
            "columns_mart",
            invocation=checks,
            at=B3,
            status="pass",
            test_type="anomaly_detection",
            sub_type="null_percent",
            column="name",
        ),
        dimension,
        _result("freshness_nws", invocation=checks, at=B3, status="pass", test_type="anomaly_detection"),
        _result(
            "schema_dec",
            invocation=checks,
            at=B3,
            status="warn",
            test_type="schema_change",
            sub_type="column_added",
            column="surface",
            schema_table=capitals,
        ),
        _result(
            "schema_dec",
            invocation=checks,
            at=B3,
            status="warn",
            test_type="schema_change",
            sub_type="column_removed",
            column="old_col",
            schema_table=capitals,
        ),
        _result(
            "schema_mystery",
            invocation=checks,
            at=B3,
            status="warn",
            test_type="schema_change",
            sub_type="column_added",
            column="secret_column",
        ),
        _result("exposure_schema_mart", invocation=checks, at=B3, status="pass"),
    ]
    rows += [
        # The bucket before the anomalous one scored inside the band, then the anomaly at this build's bucket.
        _anomaly_row(volume["id"], B2, 5262.0, 5100.0, 5400.0, False),
        _anomaly_row(volume["id"], B3, 4118.0, 5231.3, 5292.7, True),
        _anomaly_row(secret["id"], B3, 12.0, 100.0, 120.0, True),
        _anomaly_row(mart_volume["id"], _hours_before(B3, 30), 1030.0, 985.0, 1015.0, False, at=B3),
        _anomaly_row(mart_volume["id"], B3, 1000.0, 990.0, 1010.0, False),
        _anomaly_row(closures_rows["id"], B3, 40.0, 50.0, 60.0, True),
        _anomaly_row(closures_fresh["id"], B3, 90000.0, 0.0, 86400.0, True, metric="freshness"),
        _anomaly_row(null_count["id"], B3, 7.0, 0.0, 2.5, True, metric="null_count", column="name"),
        _anomaly_row(smallest["id"], B3, 0.1234, 10.0, 20.0, True, metric="min", column="distance_ft"),
        _anomaly_row(status_nulls["id"], B3, 4.0, 0.0, 1.0, True, metric="null_count", column="status"),
        _anomaly_row(status_rate["id"], B3, 99.76, 99.633, 99.746, True, metric="null_percent", column="status"),
        _anomaly_row(
            dimension["id"], B3, 2.0, 30.0, 40.0, True, metric="dimension", dimension="club", dimension_value="SECRET-CLUB"
        ),
    ]
    dec_table, secret_table = "WAREHOUSE.RAW.RAW_NYSDEC__DEC_HIKING_TRAILS", "WAREHOUSE.RAW.RAW_SECRET__SECRET_LAYER"
    mart_table, closures_table = "WAREHOUSE.MARTS.TRAIL_LINES_V1", "WAREHOUSE.MARTS.CLOSURES_V1"
    # The trail_lines mart measured every hour for 200 hours to this build's bucket, all inside its check's 14 days:
    # more points than a series keeps.
    metrics += [(mart_table, _hours_before(B3, k), 1000.0 + k, _hours_before(B3, k), "row_count") for k in range(200)]
    metrics += [
        (closures_table, B1, 52.0, B1, "row_count"),
        (closures_table, B2, 55.0, B2, "row_count"),
        (closures_table, B3, 40.0, B3, "row_count"),
        (closures_table, B1, 3000.0, B1, "freshness"),
        (closures_table, B2, 3600.0, B2, "freshness"),
        (closures_table, B3, 90000.0, B3, "freshness"),
        # Outside the check's 14 days: left out of its series.
        (dec_table, "2026-09-01 07:05:00", 5100.0, "2026-09-01 07:05:00", "row_count"),
        (dec_table, B1, 5240.0, B1, "row_count"),
        (dec_table, B2, 5262.0, B2, "row_count"),
        # Elementary appends a recomputed bucket under the same id: the newer row wins.
        (dec_table, B3, 4000.0, "2026-10-08 07:04:00", "row_count"),
        (dec_table, B3, 4118.0, B3, "row_count"),
        (secret_table, B3, 12.0, B3, "row_count"),
    ]
    # Column metrics, named by Elementary in capitals: two columns' null counts, one's null rate, and a minimum, which
    # is one row's own value and never charted.
    for column, metric, values in (
        ("NAME", "null_count", (1.0, 2.0, 7.0)),
        ("STATUS", "null_count", (0.0, 1.0, 4.0)),
        # A 4-byte FLOAT, as Elementary stores a metric: 99.76 reads back as 99.76000213623047 unless widened first.
        ("STATUS", "null_percent", (99.706, 99.711, 99.76)),
        ("DISTANCE_FT", "min", (0.5, 0.25, 0.1234)),
    ):
        metrics += [(mart_table, at, value, at, metric, column) for at, value in zip((B1, B2, B3), values, strict=True)]
    return results, rows, metrics


def _warehouse(path: Path, *, empty: bool = False) -> None:
    results, rows, metrics = ([], [], []) if empty else _history()
    freshness = [] if empty else FRESHNESS
    with duckdb.connect(str(path)) as con:
        for schema in ("elementary", "intermediate", "seeds"):
            con.execute(f"create schema {schema}")
        con.execute(
            """create table elementary.elementary_test_results (
                id varchar, test_unique_id varchar, model_unique_id varchar, invocation_id varchar,
                detected_at timestamp, created_at timestamp, database_name varchar, schema_name varchar,
                table_name varchar, column_name varchar, test_type varchar, test_sub_type varchar,
                test_short_name varchar, status varchar, failures bigint, test_results_description varchar,
                other varchar, result_rows varchar, test_params varchar)"""
        )
        columns = list(_result("not_null_dec_name", invocation="x", at=B1, status="pass"))
        for result in results:
            con.execute(
                f"insert into elementary.elementary_test_results ({', '.join(columns)}) values ({', '.join('?' * len(columns))})",
                [result[column] for column in columns],
            )
        con.execute(
            """create table elementary.test_result_rows (elementary_test_results_id varchar, result_row varchar,
                detected_at timestamp, created_at timestamp, row_index integer, test_type varchar)"""
        )
        for row in rows:
            con.execute(
                "insert into elementary.test_result_rows values (?, ?, ?, ?, ?, ?)",
                [
                    row[key]
                    for key in ("elementary_test_results_id", "result_row", "detected_at", "created_at", "row_index", "test_type")
                ],
            )
        con.execute(
            """create table elementary.data_monitoring_metrics (id varchar, full_table_name varchar, column_name varchar,
                metric_name varchar, metric_value float, source_value varchar, bucket_start timestamp,
                bucket_end timestamp, updated_at timestamp, dimension varchar, dimension_value varchar)"""
        )
        # A metric row's id is its table, column, metric and bucket (and settings, here none), as Elementary's is, so
        # a recomputed bucket's rows share one.
        for table, bucket, value, updated, metric, *column in metrics:
            name = column[0] if column else None
            con.execute(
                "insert into elementary.data_monitoring_metrics values (?, ?, ?, ?, ?, 'SECRET-SOURCE-VALUE', "
                "null, ?, ?, null, null)",
                [f"{table}|{name}|{metric}|{bucket}", table, name, metric, value, bucket, updated],
            )
        for table in ("dbt_models", "dbt_snapshots"):
            con.execute(
                f"""create table elementary.{table} (unique_id varchar, original_path varchar, depends_on_nodes varchar,
                    alias varchar, name varchar)"""
            )
        for table, nodes in (("dbt_models", MODELS), ("dbt_snapshots", SNAPSHOTS)):
            for uid, (path_, parents) in nodes.items():
                con.execute(
                    f"insert into elementary.{table} values (?, ?, ?, ?, ?)",
                    [uid, path_, json.dumps(parents), _table_of(uid)[1], uid.split(".")[2]],
                )
        con.execute("create table elementary.dbt_seeds (unique_id varchar, alias varchar, name varchar)")
        con.execute("insert into elementary.dbt_seeds values ('seed.ourhike.poi_types', 'poi_types', 'poi_types')")
        con.execute(
            "create table elementary.dbt_sources (unique_id varchar, source_name varchar, name varchar, identifier varchar)"
        )
        for uid, (group, table) in SOURCES.items():
            con.execute("insert into elementary.dbt_sources values (?, ?, ?, ?)", [uid, group, table, table])
        con.execute(
            """create table elementary.dbt_tests (unique_id varchar, original_path varchar, depends_on_nodes varchar,
                parent_model_unique_id varchar, short_name varchar, error_if varchar, meta varchar)"""
        )
        for name, (short, parent, depends, path_) in TESTS.items():
            error_if, meta = THRESHOLDS.get(name, (">0", {}))
            con.execute(
                "insert into elementary.dbt_tests values (?, ?, ?, ?, ?, ?, ?)",
                [_uid(name), path_, json.dumps(depends or [parent]), parent, short, error_if, json.dumps(meta)],
            )
        # Elementary 0.26.0's columns for it, as they read on dbt 2.0.6 and DuckDB (measured 2026-10-15).
        con.execute(
            """create table elementary.dbt_source_freshness_results (source_freshness_execution_id varchar,
                unique_id varchar, max_loaded_at varchar, snapshotted_at varchar, generated_at varchar,
                created_at timestamp, max_loaded_at_time_ago_in_s float, status varchar, error varchar,
                invocation_id varchar, warn_after varchar, error_after varchar)"""
        )
        for row in freshness:
            con.execute(
                f"insert into elementary.dbt_source_freshness_results ({', '.join(row)}) values ({', '.join('?' * len(row))})",
                list(row.values()),
            )
        con.execute("create table intermediate.int_sources__publication (source_key varchar, may_publish boolean)")
        con.executemany("insert into intermediate.int_sources__publication values (?, ?)", PUBLICATION)
        con.execute("create table seeds.notice_readers (source_key varchar, raw_table varchar)")
        con.executemany("insert into seeds.notice_readers values (?, ?)", NOTICE_READERS)
        con.execute("create table intermediate.int_sources__final (source_key varchar, title varchar, may_publish boolean)")
        con.executemany("insert into intermediate.int_sources__final values (?, ?, ?)", FINAL_SOURCES)
        con.execute("create table intermediate.int_sources__data_edited (source_key varchar, data_edited_on varchar)")
        con.executemany("insert into intermediate.int_sources__data_edited values (?, ?)", DATA_EDITED)


def _build(root: Path, *, empty: bool = False) -> dict[str, dict]:
    """Both writers, built by dbt over a warehouse of Elementary-shaped tables; their two files, read back."""
    warehouse, processed = root / "warehouse.duckdb", root / "processed"
    processed.mkdir(parents=True)
    _warehouse(warehouse, empty=empty)
    env = {
        **os.environ,
        "OURHIKE_WAREHOUSE": str(warehouse),
        "OURHIKE_PROCESSED_DIR": str(processed),
        "OURHIKE_ELEMENTARY": "true",
        "OURHIKE_BUILD_STARTED_AT": STARTED,
        "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS": "false",
        "TZ": "UTC",
    }
    paths = ("--target-path", str(root / "target"), "--log-path", str(root / "logs"))
    completed = subprocess.run(
        [DBT, "build", "-s", "pub_data_quality", "pub_conditions_data_quality", "--profiles-dir", ".", *paths],
        cwd=DBT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-2000:]
    return {
        "monthly": json.loads((processed / "data_quality.json").read_text(encoding="utf-8")),
        "hourly": json.loads((processed / "conditions_data_quality.json").read_text(encoding="utf-8")),
        "raw": (processed / "data_quality.json").read_text(encoding="utf-8")
        + (processed / "conditions_data_quality.json").read_text(encoding="utf-8"),
    }


@pytest.fixture(scope="module")
def files(tmp_path_factory) -> dict[str, dict]:
    return _build(tmp_path_factory.mktemp("data_quality"))


@pytest.fixture(scope="module")
def empty_files(tmp_path_factory) -> dict[str, dict]:
    return _build(tmp_path_factory.mktemp("data_quality_empty"), empty=True)


def _counts(checks: int, passed: int, warned: int, failed: int, errored: int) -> dict:
    return {"checks": checks, "passed": passed, "warned": warned, "failed": failed, "errored": errored}


def test_each_lanes_file_names_its_format_lane_and_when_it_was_built(files):
    for lane in ("monthly", "hourly"):
        document = files[lane]
        assert list(document) == [
            "format",
            "lane",
            "built_at",
            "totals",
            "kinds",
            "learning",
            "needs_a_look",
            "series",
            "by_mart",
            "last_posts",
        ]
        assert (document["format"], document["lane"]) == ("ourhike-data-quality/1", lane)
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", document["built_at"]), document["built_at"]
    differ = ("lane", "built_at", "last_posts")
    assert {key: value for key, value in files["monthly"].items() if key not in differ} == {
        key: value for key, value in files["hourly"].items() if key not in differ
    }, "both read the same tables; only the lane, the stamp and the monthly lane's last posts differ"


def test_this_builds_counted_checks_by_kind_a_held_source_neither_named_nor_counted(files):
    """28 checks count. Left out: every check a held source reaches (secret_layer's raw table, its staging, the
    union of it with dec's, the snapshot of that union, a singular test reading it), the mystery table the registry
    has no row for, the club whose notice_readers row names a held key though its own name publishes, a step's
    derived table that shares a registry key's name, a test Elementary's dbt_tests does not hold, and a skipped test.
    The retried test counts once, as its retry passed. Earlier builds' results are history, not this build's.
    Freshness is the five sources' dbt freshness this build measured (FRESHNESS); Elementary's freshness_anomalies on
    NWS and the freshness half of the closures mart's table_anomalies test count nowhere."""
    document = files["monthly"]

    # The mart's not_null on `name` warned with 5 past its error_if of >0: failed.
    assert document["totals"] == _counts(28, 11, 12, 3, 2)
    assert document["kinds"] == [
        {"kind": "freshness", **_counts(5, 1, 2, 1, 1)},
        {"kind": "volume", **_counts(3, 1, 2, 0, 0)},
        {"kind": "schema", **_counts(2, 1, 1, 0, 0)},
        {"kind": "dbt_tests", **_counts(12, 7, 2, 2, 1)},
        {"kind": "anomalies", **_counts(6, 1, 5, 0, 0)},
    ]


def test_needs_a_look_is_worst_first_and_each_entry_carries_only_numbers_and_names(files):
    """`since` is the file's own built_at for a run of warnings that began in this build, which the page reads as
    "since this build" (site/src/lib/dataQuality.mjs), and a date for one that began earlier. `metric` is an
    anomaly check's alone: a dbt test's and a schema change's are null (the contract as amended 2026-10-08)."""
    document = files["monthly"]
    look, now, last_build = document["needs_a_look"], document["built_at"], "2026-10-07T07:05:00Z"
    source = "source_freshness", "last_read_age"

    def entry(kind, table, column, status, value, low, high, since, metric, test):
        return {
            "kind": kind,
            "table": table,
            "column": column,
            "status": status,
            "value": value,
            "expected_min": low,
            "expected_max": high,
            "since": since,
            "metric": metric,
            "test": test,
        }

    dec = "raw_nysdec__dec_hiking_trails"
    assert look == [
        # An error measured nothing: a source's runtime error, then a test's.
        entry("freshness", "raw_nysparks__oprhp_trail_closures", None, "error", None, None, None, None, *reversed(source)),
        entry("dbt_tests", "int_trail_lines__after_the_mart", "id", "error", None, None, None, now, None, "relationships"),
        # Past its error limit: seconds since the extract last read it or confirmed it unchanged, against the error
        # limit, also in seconds. No `since`: the value is how long.
        entry("freshness", "raw_nws__alerts", None, "fail", 11250, None, 7200.0, None, *reversed(source)),
        # Warned with 5 past its error_if of >0, so failed. Passed in the build before: since this build.
        entry("dbt_tests", "trail_lines_v1", "name", "fail", 5, None, None, now, None, "not_null"),
        entry("dbt_tests", "trail_lines_v1", "status", "fail", 2, None, None, now, None, "accepted_values"),
        # No error limit (reaches_hikers false): the warning limit is the one quoted.
        entry("freshness", "raw_atc__challenges_atc", None, "warn", 46800, None, 43200.0, None, *reversed(source)),
        entry("freshness", "raw_registry__sources", None, "warn", 3456000, None, 5356800.0, None, *reversed(source)),
        entry("volume", "closures_v1", None, "warn", 40, 50.0, 60.0, now, "row_count", "table_anomalies"),
        # Warned in build 2 too, after passing in build 1: since build 2. A row count is a whole number.
        entry("volume", dec, None, "warn", 4118, 5231.3, 5292.7, last_build, "row_count", "volume_anomalies"),
        # One entry per changed column, the table's capitals lowered.
        entry("schema", dec, "old_col", "warn", None, None, None, now, None, "schema_changes"),
        entry("schema", dec, "surface", "warn", None, None, None, now, None, "schema_changes"),
        # Elementary named no table for a test of two: the first by name of the two it reads.
        # Past its error_if, and kept a warning by its meta's stays_at_warn.
        entry("dbt_tests", "int_trail_lines__checked", None, "warn", 6, None, None, now, None, "assert_lines_match_checks"),
        # A level of 1, below its error_if of >1, and no count: no value.
        entry("dbt_tests", "stg_atc__challenges", "id", "warn", None, None, None, now, None, "not_null"),
        # A column's minimum is one row's own value: its numbers are never written.
        entry("anomalies", "trail_lines_v1", "distance_ft", "warn", None, None, None, now, "min", "column_anomalies"),
        entry("anomalies", "trail_lines_v1", "name", "warn", 7, 0.0, 2.5, now, "null_count", "column_anomalies"),
        # A rate in Elementary's percent, to 3 places.
        entry("anomalies", "trail_lines_v1", "status", "warn", 4, 0.0, 1.0, now, "null_count", "column_anomalies"),
        entry("anomalies", "trail_lines_v1", "status", "warn", 99.76, 99.633, 99.746, now, "null_percent", "column_anomalies"),
        # How many dimension values are out of band, never which.
        entry("anomalies", "trail_lines_v1", None, "warn", 3, None, None, now, "dimension", "dimension_anomalies"),
    ]


#: Each series as the file writes it, each band where that series' check scored the bucket and null where no kept
#: run did. The closures mart's table check's row count, its freshness metric charted nowhere. A mart's
#: table is named by version, and `mart` names its folder, as by_mart does.
CLOSURES_SERIES = [
    {
        "table": "closures_v1",
        "column": None,
        "metric": "row_count",
        "mart": "closures",
        "in_needs_a_look": True,
        "points": [
            {"at": "2026-10-06T07:05:00Z", "value": 52, "expected_min": None, "expected_max": None},
            {"at": "2026-10-07T07:05:00Z", "value": 55, "expected_min": 50.0, "expected_max": 60.0},
            {"at": "2026-10-08T07:05:00Z", "value": 40, "expected_min": 50.0, "expected_max": 60.0},
        ],
    },
]
DEC_SERIES = {
    "table": "raw_nysdec__dec_hiking_trails",
    "column": None,
    "metric": "row_count",
    "mart": None,
    "in_needs_a_look": True,
    "points": [
        {"at": "2026-10-06T07:05:00Z", "value": 5240, "expected_min": None, "expected_max": None},
        {"at": "2026-10-07T07:05:00Z", "value": 5262, "expected_min": 5100.0, "expected_max": 5400.0},
        {"at": "2026-10-08T07:05:00Z", "value": 4118, "expected_min": 5231.3, "expected_max": 5292.7},
    ],
}


def _column_series(column: str, metric: str, values: tuple, band: tuple[float, float]) -> dict:
    """A trail_lines column's metric over the three builds, banded at this build's bucket alone."""
    points = [
        {"at": at, "value": value, "expected_min": None, "expected_max": None}
        for at, value in zip(("2026-10-06T07:05:00Z", "2026-10-07T07:05:00Z", "2026-10-08T07:05:00Z"), values, strict=True)
    ]
    points[-1].update({"expected_min": band[0], "expected_max": band[1]})
    return {
        "table": "trail_lines_v1",
        "column": column,
        "metric": metric,
        "mart": "trail_lines",
        "in_needs_a_look": True,
        "points": points,
    }


#: Two columns' null counts on one table, told apart by their column, and a null rate to 3 places.
COLUMN_SERIES = [
    _column_series("name", "null_count", (1, 2, 7), (0.0, 2.5)),
    _column_series("status", "null_count", (0, 1, 4), (0.0, 1.0)),
    _column_series("status", "null_percent", (99.706, 99.711, 99.76), (99.633, 99.746)),
]


#: The trail_lines mart's bands, by hours before this build's bucket: the oldest hour the series keeps from build 2's
#: kept run, which alone scored it; the hour both runs scored from this build's, the newer; and this build's own.
TRAIL_LINES_BANDS = {167: (1100.0, 1300.0), 30: (985.0, 1015.0), 0: (990.0, 1010.0)}


def _trail_lines_series() -> dict:
    """The trail_lines mart's newest 168 hourly points of the 200 it has, oldest first, each banded by the newest run
    that scored it, kept or this build's, and unbanded where none did."""
    points = []
    for hours in range(167, -1, -1):
        at = (datetime.fromisoformat(B3) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        low, high = TRAIL_LINES_BANDS.get(hours, (None, None))
        points.append({"at": at, "value": 1000 + hours, "expected_min": low, "expected_max": high})
    return {
        "table": "trail_lines_v1",
        "column": None,
        "metric": "row_count",
        "mart": "trail_lines",
        "in_needs_a_look": False,
        "points": points,
    }


def test_the_series_are_every_marts_row_count_and_each_entrys_metric_the_newest_168_points_of_each(files):
    """The scope the maintainer chose by poll (2026-10-08): every mart's row count this build measured, needing a
    look or not, and the history behind each needs_a_look entry whose metric is a count, a rate or an age, a table's
    or a column's, needs-a-look series first. One series per table, column and metric: the closures mart's row
    count, named both ways, appears once, and trail_lines' two null counts are two series. A null rate is written to
    3 places from its 4-byte FLOAT, 99.76 and not 99.76000213623047, so the page finds its entry's point by value
    (the review of 2026-10-15, thread 4279329354). The point outside the dec
    check's 14 days is left out, the rewritten bucket's newer row wins, the held source's metric has no series, nor
    has the column minimum or the dimension, and the trail_lines mart's 200 hourly points are cut to the newest 168."""
    series = files["monthly"]["series"]

    assert series == [*CLOSURES_SERIES, DEC_SERIES, *COLUMN_SERIES, _trail_lines_series()]
    assert [len(entry["points"]) for entry in series] == [3, 3, 3, 3, 3, 168]


def test_a_point_this_builds_run_did_not_score_takes_the_band_row_history_kept_and_a_rescored_one_the_newest(files):
    """row_history.py keeps each bucket's newest band, its BAND_FIELDS alone ("THE BANDS"): the oldest hour the
    trail_lines series keeps is banded by build 2's kept run, and the hour both runs scored by this build's."""
    (trail_lines,) = [entry for entry in files["monthly"]["series"] if entry["table"] == "trail_lines_v1" and not entry["column"]]
    banded = {
        point["at"]: (point["expected_min"], point["expected_max"])
        for point in trail_lines["points"]
        if point["expected_min"] is not None
    }
    assert banded == {
        "2026-10-01T08:05:00Z": (1100.0, 1300.0),
        "2026-10-07T01:05:00Z": (985.0, 1015.0),
        "2026-10-08T07:05:00Z": (990.0, 1010.0),
    }


def test_learning_counts_the_builds_and_needs_the_11_points_anomaly_sensitivity_3_takes(files):
    """needed: the least n whose (n - 1) / sqrt(n) is above dbt_project.yml's anomaly_sensitivity of 3, so the
    least window in which a point can score past it (macros/data_quality.sql's header, "learning")."""
    assert files["monthly"]["learning"] == {"builds": 3, "needed": 11}


def test_by_mart_counts_the_marts_own_models_intermediates_and_singular_tests(files):
    """trail_lines: its mart's tests and checks, the intermediate after the mart and the one reading the registry,
    and its folder's two singular tests; its union, held, is not among them. closures: its table check's two."""
    assert files["monthly"]["by_mart"] == [
        {"mart": "closures", **_counts(1, 0, 1, 0, 0)},
        {"mart": "trail_lines", **_counts(14, 5, 6, 2, 1)},
    ]


def test_nothing_but_counts_and_names_leaves_the_warehouse(files):
    raw = files["raw"]
    for planted in (*SECRETS, *HELD_NAMES, "secret_column", "unique_secret_id"):
        assert planted not in raw, planted
    names = {
        "ourhike-data-quality/1",
        "monthly",
        "hourly",
        "freshness",
        "volume",
        "schema",
        "dbt_tests",
        "anomalies",
        "warn",
        "fail",
        "error",
        "raw_nysdec__dec_hiking_trails",
        "raw_nws__alerts",
        "raw_nysparks__oprhp_trail_closures",
        "raw_registry__sources",
        "raw_atc__challenges_atc",
        "source_freshness",
        "last_read_age",
        "int_trail_lines__after_the_mart",
        "int_trail_lines__checked",
        "stg_atc__challenges",
        "trail_lines",
        "trail_lines_v1",
        "closures",
        "closures_v1",
        "table_anomalies",
        "id",
        "name",
        "status",
        "surface",
        "old_col",
        "distance_ft",
        "relationships",
        "accepted_values",
        "not_null",
        "assert_lines_match_checks",
        "volume_anomalies",
        "schema_changes",
        "column_anomalies",
        "dimension_anomalies",
        "row_count",
        "min",
        "null_count",
        "null_percent",
        "dimension",
    }

    def leaves(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from leaves(item)
        elif isinstance(value, list):
            for item in value:
                yield from leaves(item)
        else:
            yield value

    for lane in ("monthly", "hourly"):
        # last_posts names published sources by key and title, and dates them; its own test below holds it.
        for leaf in leaves({key: value for key, value in files[lane].items() if key != "last_posts"}):
            if isinstance(leaf, str):
                assert leaf in names or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", leaf), leaf
            else:
                assert leaf is None or isinstance(leaf, (int, float)), leaf


def test_a_lane_whose_history_holds_no_result_writes_zeros_and_empty_lists(empty_files):
    document = empty_files["monthly"]

    assert document["totals"] == _counts(0, 0, 0, 0, 0)
    assert [kind["checks"] for kind in document["kinds"]] == [0, 0, 0, 0, 0]
    assert document["learning"] == {"builds": 0, "needed": 11}
    assert (document["needs_a_look"], document["series"], document["by_mart"]) == ([], [], [])


def test_a_null_rates_last_point_is_its_entrys_own_value(files):
    """The page finds the point an entry is about by its value (site/src/lib/dataQuality.mjs, pointOf()). On UA's
    hourly file of 2026-10-15 every null-rate row said "No earlier range to compare it with", because the entry read
    99.76 off its scored row's double while the series wrote Elementary's FLOAT as 99.76000213623047."""
    document = files["monthly"]
    (entry,) = [item for item in document["needs_a_look"] if (item["column"], item["metric"]) == ("status", "null_percent")]
    (series,) = [item for item in document["series"] if (item["column"], item["metric"]) == ("status", "null_percent")]
    assert entry["value"] == series["points"][-1]["value"] == 99.76
    assert [point["value"] for point in series["points"]] == [99.706, 99.711, 99.76]


def test_each_sources_freshness_is_its_last_result_in_this_build_and_elementarys_learned_freshness_counts_nowhere(files):
    """Decision 203 (the maintainer, 2026-10-15): freshness is OurHike's own last successful read of a source. dec,
    measured twice, counts once, by its pass; the build before's result, the held secret layer's and a source
    Elementary does not describe count nowhere and are named nowhere. Elementary's freshness_anomalies result and the
    closures table check's freshness metric are neither counted, nor an entry, nor a series."""
    document = files["monthly"]
    freshness = [item for item in document["needs_a_look"] if item["kind"] == "freshness"]
    assert {item["table"] for item in freshness} == {
        "raw_nysparks__oprhp_trail_closures",
        "raw_nws__alerts",
        "raw_atc__challenges_atc",
        "raw_registry__sources",
    }
    assert all((item["test"], item["metric"], item["since"]) == ("source_freshness", "last_read_age", None) for item in freshness)
    learned = ("freshness", "event_freshness", "freshness_anomalies", "event_freshness_anomalies")
    assert not [item for item in document["needs_a_look"] if item["metric"] in learned or item["test"] in learned]
    assert not [item for item in document["series"] if item["metric"] in learned]
    assert "raw_ghost__layer" not in files["raw"] and "raw_secret__secret_layer" not in files["raw"]


def test_last_posts_date_each_published_source_by_its_own_layer_and_warn_about_none(files, empty_files):
    """The rule 23 (the maintainer's poll, 2026-10-15, "Not now, show last post"): no gap-based freshness
    warning, each source's last post shown as information instead. The monthly file lists every published source
    whose layer states an edit date, by title; a held source is neither named nor dated; nothing about it is counted,
    so totals and needs_a_look are what they were; the hourly lane reads no layer's date and lists none."""
    assert files["monthly"]["last_posts"] == [
        {"source": "dec_hiking_trails", "title": "DEC hiking trails", "edited_on": "2026-09-18"},
        {"source": "oprhp_trail_closures", "title": "OPRHP temporary trail closures", "edited_on": "2026-10-07"},
    ]
    assert files["hourly"]["last_posts"] == []
    assert "SECRET-HELD-TITLE" not in files["raw"] and "2001-01-01" not in files["raw"]
    assert not [
        item for item in files["monthly"]["needs_a_look"] if item["table"] in ("dec_hiking_trails", "oprhp_trail_closures")
    ]
    assert empty_files["hourly"]["last_posts"] == []
