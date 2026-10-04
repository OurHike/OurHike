"""A real dbt build of the clubs' generated layers on a warehouse that holds none of their raw tables.

A source that has never landed is a missing table: a monthly layer the
extract refused on its first run (extract/_run.py's ISOLATING_LANES leaves it
out and loads the rest), or a keyed API whose key the job lacks. Every base
model pipeline/make_dbt_staging.py writes reads its raw table through
raw_or_empty() (dbt/macros/raw_or_empty.sql), so a missing table reads as no
rows with the columns its models name, and the build goes on. This builds the
widest case on the fixtures: every generated layer's raw table dropped and
its run-log rows deleted. Then:

(a) the build succeeds, its tests included, through every model that reads
    the generated layers: the club points' rules, the club trail lines,
    places, elevation, the source extents and the four content unions;
(b) each dropped table's base model exists and reads no rows, and so does
    every club union and rule model above them.

It stops short of the hand-staged chain (int_points_of_interest__unioned and
what reads it), which also reads the `derived` schema build_marts.py's Python
steps write before dbt runs, and which this test does not run. The fixture
build's full monthly selection covers that chain with every layer present.

A layer that landed once never reads as absent: the extract keeps its last
committed table when a later read fails (tests/test_extract_run.py's
monthly isolation tests), and the warehouse loads that.

It needs dbt 2.0.6 with the packages under pipeline/dbt/dbt_packages/, and
runs only when OURHIKE_DBT names that dbt, as
tests/test_dbt_notice_tables_absent_builds.py does.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest
import yaml

PIPELINE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = PIPELINE_DIR / "dbt"
DBT = os.environ.get("OURHIKE_DBT")
#: The Python that runs extract._fixtures, which imports dlt (tests/test_dbt_notice_tables_absent_builds.py says why).
EXTRACT_PYTHON = os.environ.get("OURHIKE_EXTRACT_PYTHON") or sys.executable
pytestmark = pytest.mark.skipif(not DBT, reason="OURHIKE_DBT names no dbt (the dbt job and scripts/test.sh set it)")

#: Every model that reads a generated layer's base or staging model, upstream of nothing it does not need.
READERS = (
    "int_points_of_interest__club_points",
    "int_trail_lines__club_lines",
    "int_trail_lines__source_extents",
    "int_places__source_extents",
    "int_elevation__club_samples",
    "int_elevation__source_extents",
    "int_podcasts__club_unioned",
    "int_suggested_hikes__club_unioned",
    "int_challenges__club_unioned",
    "int_photos__club_unioned",
)


def _generated_tables() -> dict[str, str]:
    """{raw table: its base model}, from every source file make_dbt_staging.py writes."""
    found = {}
    for path in (DBT_DIR / "models" / "staging").glob("*/_*__generated__sources.yml"):
        for source in yaml.safe_load(path.read_text())["sources"]:
            folder = source["name"]
            for table in source["tables"]:
                found[table["name"]] = f"base_{folder}__{table['name'].removeprefix(f'raw_{folder}__')}"
    return found


def _run(arguments: list[str], cwd: Path, env: dict) -> None:
    completed = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-2000:]


@pytest.fixture(scope="module")
def build(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("club_tables_absent")
    raw, warehouse, processed = root / "raw", root / "warehouse.duckdb", root / "processed"
    processed.mkdir()
    env = {**os.environ, "RUNTIME__DLTHUB_TELEMETRY": "false", "TZ": "UTC"}
    _run([sys.executable, "make_dbt_fixtures.py", "--raw-dir", str(raw)], PIPELINE_DIR, env)
    _run(
        [
            EXTRACT_PYTHON,
            "-m",
            "extract._fixtures",
            "--raw-dir",
            str(raw),
            "--warehouse",
            str(warehouse),
            "--store",
            str(root / "store"),
        ],
        PIPELINE_DIR,
        env,
    )

    generated = _generated_tables()
    with duckdb.connect(str(warehouse)) as con:
        present = {
            name
            for (name,) in con.execute("select table_name from information_schema.tables where table_schema = 'raw'").fetchall()
        }
        dropped = sorted(set(generated) & present)
        for table in dropped:
            con.execute(f'drop table raw."{table}"')
        con.execute("delete from raw._extract_runs where list_contains(?, table_name)", [sorted(generated)])

    dbt_env = {
        **env,
        "OURHIKE_WAREHOUSE": str(warehouse),
        "OURHIKE_PROCESSED_DIR": str(processed),
        "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS": "false",
        "OURHIKE_ROW_HISTORY": "off",
    }
    paths = ["--profiles-dir", ".", "--target-path", str(root / "target"), "--log-path", str(root / "logs")]
    _run([DBT, "seed", *paths], DBT_DIR, dbt_env)
    # Every generated base model too: a lookup's (a hike type's terms) is read by no union, so no reader pulls it in.
    selection = [*(f"+{model}" for model in READERS), *sorted(generated.values())]
    _run(
        [DBT, "build", "-s", *selection, "--exclude", "resource_type:snapshot", "--indirect-selection", "cautious", *paths],
        DBT_DIR,
        dbt_env,
    )
    with duckdb.connect(str(warehouse), read_only=True) as con:
        con.execute("load spatial")  # the base models are views that cast their geometry
        relations = {
            name
            for (name,) in con.execute(
                "select table_name from information_schema.tables where table_schema = 'staging'"
            ).fetchall()
        }
        base_rows = {
            generated[table]: con.execute(f'select count(*) from staging."{generated[table]}"').fetchone()[0]
            for table in dropped
            if generated[table] in relations
        }
        readers = {model: con.execute(f'select count(*) from intermediate."{model}"').fetchone()[0] for model in READERS}
    return {"dropped": dropped, "base_rows": base_rows, "readers": readers}


def test_the_build_dropped_every_generated_layer_and_still_succeeded(build):
    assert len(build["dropped"]) > 250, "the fixture warehouse held generated layers to drop"


def test_each_dropped_layers_base_model_reads_no_rows(build):
    assert set(build["base_rows"]) and len(build["base_rows"]) == len(build["dropped"]), "every base model was built"
    assert {rows for rows in build["base_rows"].values()} == {0}


def test_every_club_union_and_rule_model_is_built_and_reads_no_rows(build):
    assert build["readers"] == dict.fromkeys(READERS, 0)
