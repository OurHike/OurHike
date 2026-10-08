"""The data-quality page's two files, built by dbt from Elementary-shaped tables (decision 102, step 4).

The warehouse here holds what pub_data_quality and pub_conditions_data_quality
read, in the shapes Elementary 0.26.0 writes them on dbt 2.0.6 and DuckDB
(read off a scratch project's tables, 2026-10-08, macros/data_quality.sql's
header): three builds of one lane's history, each check of the third (this
build) chosen to reach one rule of the file, and a project graph in which two
raw tables publish, three are held, one is OurHike's own registry, and one is
a step's derived table. Then the two writers are built, with Elementary on,
and each file is read field by field: what counts, what is named, the order of
what needs a look, since when, the series and its window, the learning count,
and that no row value, sample, coordinate, check message or held table's name
reaches either. A second warehouse holds no result at all, and two more builds
of the monthly writer widen its series by the one parameter that scopes it.

Run by the dbt job, which sets OURHIKE_DBT, as the other *_builds.py files are;
the pytest job, which has no dbt, skips.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import duckdb
import pytest

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
CLUB = "source.ourhike.club.raw_club__club_news"
DERIVED = "source.ourhike.derived.osm_water"
SOURCES = {
    DEC: ("dec", "raw_nysdec__dec_hiking_trails"),
    SECRET: ("secret", "raw_secret__secret_layer"),
    MYSTERY: ("mystery", "raw_mystery__mystery_layer"),
    REGISTRY: ("registry", "raw_registry__sources"),
    NWS: ("nws", "raw_nws__alerts"),
    ATC_CHALLENGES: ("atc", "raw_atc__challenges_atc"),
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
    ("club_news", True),
    ("club_notices", False),
    ("osm_water", True),
]
NOTICE_READERS = [("club_notices", "raw_club__club_news")]

MART = "model.ourhike.trail_lines.v1"
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


def _uid(name: str) -> str:
    return f"test.ourhike.{name}"


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
    name = parent.split(".")[2]
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


def _anomaly_row(result_id: str, bucket: str, value: float, low: float | None, high: float | None, anomalous: bool, **extra):
    return {
        "elementary_test_results_id": result_id,
        "test_type": "anomaly_detection",
        "created_at": bucket,
        "detected_at": bucket,
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
    # The mart's row count, inside its band: in no needs_a_look entry, so charted only by a wider series scope.
    mart_volume = _result(
        "volume_mart", invocation=checks, at=B3, status="pass", test_type="anomaly_detection", sub_type="row_count"
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
    dimension = _result(
        "dimension_mart", invocation=checks, at=B3, status="warn", test_type="anomaly_detection", sub_type="dimension", failures=3
    )
    # Elementary names a schema change's table in capitals.
    capitals = ("RAW", "RAW_NYSDEC__DEC_HIKING_TRAILS")
    results += [
        volume,
        secret,
        mart_volume,
        null_count,
        smallest,
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
        _anomaly_row(mart_volume["id"], B3, 818.0, 800.0, 830.0, False),
        _anomaly_row(null_count["id"], B3, 7.0, 0.0, 2.5, True, metric="null_count", column="name"),
        _anomaly_row(smallest["id"], B3, 0.1234, 10.0, 20.0, True, metric="min", column="distance_ft"),
        _anomaly_row(
            dimension["id"], B3, 2.0, 30.0, 40.0, True, metric="dimension", dimension="club", dimension_value="SECRET-CLUB"
        ),
    ]
    dec_table, secret_table = "WAREHOUSE.RAW.RAW_NYSDEC__DEC_HIKING_TRAILS", "WAREHOUSE.RAW.RAW_SECRET__SECRET_LAYER"
    mart_table = "WAREHOUSE.MARTS.TRAIL_LINES"
    metrics += [
        (mart_table, B1, 812.0, B1),
        (mart_table, B2, 815.0, B2),
        (mart_table, B3, 818.0, B3),
        # Outside the check's 14 days: left out of its series.
        (dec_table, "2026-09-01 07:05:00", 5100.0, "2026-09-01 07:05:00"),
        (dec_table, B1, 5240.0, B1),
        (dec_table, B2, 5262.0, B2),
        # Elementary rewrites a recent bucket: the later row wins.
        (dec_table, B3, 4000.0, "2026-10-08 07:04:00"),
        (dec_table, B3, 4118.0, B3),
        (secret_table, B3, 12.0, B3),
    ]
    return results, rows, metrics


def _warehouse(path: Path, *, empty: bool = False) -> None:
    results, rows, metrics = ([], [], []) if empty else _history()
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
        for number, (table, bucket, value, updated) in enumerate(metrics):
            con.execute(
                "insert into elementary.data_monitoring_metrics values (?, ?, null, 'row_count', ?, 'SECRET-SOURCE-VALUE', "
                "null, ?, ?, null, null)",
                [str(number), table, value, bucket, updated],
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
                parent_model_unique_id varchar, short_name varchar)"""
        )
        for name, (short, parent, depends, path_) in TESTS.items():
            con.execute(
                "insert into elementary.dbt_tests values (?, ?, ?, ?, ?)",
                [_uid(name), path_, json.dumps(depends or [parent]), parent, short],
            )
        con.execute("create table intermediate.int_sources__publication (source_key varchar, may_publish boolean)")
        con.executemany("insert into intermediate.int_sources__publication values (?, ?)", PUBLICATION)
        con.execute("create table seeds.notice_readers (source_key varchar, raw_table varchar)")
        con.executemany("insert into seeds.notice_readers values (?, ?)", NOTICE_READERS)


def _build(root: Path, *, empty: bool = False, series: str | None = None) -> dict[str, dict]:
    """Both writers, built by dbt over a warehouse of Elementary-shaped tables; their two files, read back. With
    `series`, the monthly writer alone, its series scope set to that (macros/data_quality.sql, data_quality_series)."""
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
    writers = ("pub_data_quality",) if series else ("pub_data_quality", "pub_conditions_data_quality")
    scope = ("--vars", json.dumps({"data_quality_series": series})) if series else ()
    completed = subprocess.run(
        [DBT, "build", "-s", *writers, "--profiles-dir", ".", *paths, *scope],
        cwd=DBT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-2000:]
    if series:
        return {"monthly": json.loads((processed / "data_quality.json").read_text(encoding="utf-8"))}
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


@pytest.fixture(scope="module", params=["mart_row_counts", "published_row_counts"])
def scoped_files(request, tmp_path_factory) -> tuple[str, dict[str, dict]]:
    return request.param, _build(tmp_path_factory.mktemp(f"data_quality_{request.param}"), series=request.param)


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
        ]
        assert (document["format"], document["lane"]) == ("ourhike-data-quality/1", lane)
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", document["built_at"]), document["built_at"]
    assert {key: value for key, value in files["monthly"].items() if key not in ("lane", "built_at")} == {
        key: value for key, value in files["hourly"].items() if key not in ("lane", "built_at")
    }, "both read the same tables; only the lane and the stamp differ"


def test_this_builds_counted_checks_by_kind_a_held_source_neither_named_nor_counted(files):
    """21 checks count. Left out: every check a held source reaches (secret_layer's raw table, its staging, the
    union of it with dec's, the snapshot of that union, a singular test reading it), the mystery table the registry
    has no row for, the club whose notice_readers row names a held key though its own name publishes, a step's
    derived table that shares a registry key's name, a test Elementary's dbt_tests does not hold, and a skipped test.
    The retried test counts once, as its retry passed. Earlier builds' results are history, not this build's."""
    document = files["monthly"]

    assert document["totals"] == _counts(21, 11, 8, 1, 1)
    assert document["kinds"] == [
        {"kind": "freshness", **_counts(1, 1, 0, 0, 0)},
        {"kind": "volume", **_counts(2, 1, 1, 0, 0)},
        {"kind": "schema", **_counts(2, 1, 1, 0, 0)},
        {"kind": "dbt_tests", **_counts(12, 7, 3, 1, 1)},
        {"kind": "anomalies", **_counts(4, 1, 3, 0, 0)},
    ]


def test_needs_a_look_is_worst_first_and_each_entry_carries_only_numbers_and_names(files):
    """`since` is the file's own built_at for a run of warnings that began in this build, which the page reads as
    "since this build" (site/src/lib/dataQuality.mjs), and a date for one that began earlier. `metric` is an
    anomaly check's alone: a dbt test's and a schema change's are null (the contract as amended 2026-10-08)."""
    document = files["monthly"]
    look, now, last_build = document["needs_a_look"], document["built_at"], "2026-10-07T07:05:00Z"

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
        # An error measured nothing.
        entry("dbt_tests", "int_trail_lines__after_the_mart", "id", "error", None, None, None, now, None, "relationships"),
        entry("dbt_tests", "trail_lines", "status", "fail", 2, None, None, now, None, "accepted_values"),
        # Warned in build 2 too, after passing in build 1: since build 2. A row count is a whole number.
        entry("volume", dec, None, "warn", 4118, 5231.3, 5292.7, last_build, "row_count", "volume_anomalies"),
        # One entry per changed column, the table's capitals lowered.
        entry("schema", dec, "old_col", "warn", None, None, None, now, None, "schema_changes"),
        entry("schema", dec, "surface", "warn", None, None, None, now, None, "schema_changes"),
        # Elementary named no table for a test of two: the first by name of the two it reads.
        entry("dbt_tests", "int_trail_lines__checked", None, "warn", 6, None, None, now, None, "assert_lines_match_checks"),
        entry("dbt_tests", "stg_atc__challenges", "id", "warn", 1, None, None, now, None, "not_null"),
        # Passed in the build before, so since this build.
        entry("dbt_tests", "trail_lines", "name", "warn", 5, None, None, now, None, "not_null"),
        # A column's minimum is one row's own value: its numbers are never written.
        entry("anomalies", "trail_lines", "distance_ft", "warn", None, None, None, now, "min", "column_anomalies"),
        entry("anomalies", "trail_lines", "name", "warn", 7, 0.0, 2.5, now, "null_count", "column_anomalies"),
        # How many dimension values are out of band, never which.
        entry("anomalies", "trail_lines", None, "warn", 3, None, None, now, "dimension", "dimension_anomalies"),
    ]


#: The dec table's row counts within its check's 14 days, and the mart's: each band where that check scored a bucket.
DEC_SERIES = {
    "table": "raw_nysdec__dec_hiking_trails",
    "metric": "row_count",
    "points": [
        {"at": "2026-10-06T07:05:00Z", "value": 5240, "expected_min": None, "expected_max": None},
        {"at": "2026-10-07T07:05:00Z", "value": 5262, "expected_min": 5100.0, "expected_max": 5400.0},
        {"at": "2026-10-08T07:05:00Z", "value": 4118, "expected_min": 5231.3, "expected_max": 5292.7},
    ],
}
MART_SERIES = {
    "table": "trail_lines",
    "metric": "row_count",
    "points": [
        {"at": "2026-10-06T07:05:00Z", "value": 812, "expected_min": None, "expected_max": None},
        {"at": "2026-10-07T07:05:00Z", "value": 815, "expected_min": None, "expected_max": None},
        {"at": "2026-10-08T07:05:00Z", "value": 818, "expected_min": 800.0, "expected_max": 830.0},
    ],
}


def test_the_series_is_the_volume_checks_metric_over_its_window_with_the_band_where_one_was_scored(files):
    """The default scope, the contract's: the metric behind each volume and freshness entry of needs_a_look. The point
    outside the check's 14 days is left out, the rewritten bucket's later row wins, a build whose check scored no
    bucket has no band, the held source's metric has no series at all, and the mart's, whose check passed, none."""
    assert files["monthly"]["series"] == [DEC_SERIES]


def test_one_parameter_widens_the_series_to_every_marts_or_every_published_tables_row_count(scoped_files):
    """data_quality_series, the one parameter (macros/data_quality.sql): every table under models/marts/ whose volume
    check counted, or every table whose volume check counted. A held source's table is in neither."""
    scope, built = scoped_files
    expected = {"mart_row_counts": [MART_SERIES], "published_row_counts": [DEC_SERIES, MART_SERIES]}
    assert built["monthly"]["series"] == expected[scope]
    assert "raw_secret__secret_layer" not in json.dumps(built["monthly"])


def test_learning_counts_the_builds_whose_anomaly_checks_the_history_holds(files):
    assert files["monthly"]["learning"] == {"builds": 3, "needed": 7}


def test_by_mart_counts_the_marts_own_models_intermediates_and_singular_tests(files):
    """trail_lines: its mart's tests and checks, the intermediate after the mart and the one reading the registry,
    and its folder's two singular tests; its union, held, is not among them."""
    assert files["monthly"]["by_mart"] == [{"mart": "trail_lines", **_counts(12, 5, 5, 1, 1)}]


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
        "int_trail_lines__after_the_mart",
        "int_trail_lines__checked",
        "stg_atc__challenges",
        "trail_lines",
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
        for leaf in leaves(files[lane]):
            if isinstance(leaf, str):
                assert leaf in names or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", leaf), leaf
            else:
                assert leaf is None or isinstance(leaf, (int, float)), leaf


def test_a_lane_whose_history_holds_no_result_writes_zeros_and_empty_lists(empty_files):
    document = empty_files["monthly"]

    assert document["totals"] == _counts(0, 0, 0, 0, 0)
    assert [kind["checks"] for kind in document["kinds"]] == [0, 0, 0, 0, 0]
    assert document["learning"] == {"builds": 0, "needed": 7}
    assert (document["needs_a_look"], document["series"], document["by_mart"]) == ([], [], [])
