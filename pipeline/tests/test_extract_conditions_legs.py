"""extract/_run.py's conditions legs and its command line, as publish-conditions.yml runs them.

Each leg is the hourly lane for one data environment, in a dlt pipeline of
its own (`LEGS`), so production's and UA's OurHike rows never share a raw
table. The command line adds what the workflow's hourly job needs around a
run: the raw bucket's per-leg prefix (`--raw-bucket`), one table of a lane
(`--only`), the committed-file load into the warehouse (`--warehouse`), and
the run's evidence in the job summary (`--summary`), written on a refused
run too. Everything runs against a `file://` raw store under tmp_path, under
conftest.py's socket guard.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pytest

from extract import _run
from extract._contract import Resource
from extract._run import ExtractRefused, make_pipeline, raw_store_url, run_log_rows, run_pipeline, summary_markdown
from lib.freshness_state import Freshness


@dataclass(frozen=True)
class Answer(Resource):
    """An upstream that answers with the rows it is given, its own count, or an error."""

    answer: tuple[dict, ...] = ()
    count: int | None = None
    error: str | None = None

    def change_check(self, recorded):
        return Freshness.UNKNOWN, None

    def column_hints(self) -> dict:
        return {"id": {"data_type": "text"}}

    def rows(self, proofs):
        if self.error is not None:
            raise RuntimeError(self.error)
        if self.count is not None:
            proofs[self.table] = self.count
        yield from (dict(row) for row in self.answer)


def closures(*ids: str, count: int | None = None, error: str | None = None) -> Answer:
    return Answer(key="closures", club="ourhike", type="closures", answer=tuple({"id": i} for i in ids), count=count, error=error)


def a_monthly_layer() -> Answer:
    return Answer(key="lines", club="testclub", type="trail_lines", answer=({"id": "l1"},), count=1)


@pytest.fixture
def store(tmp_path):
    return {"url": (tmp_path / "raw-store").as_uri(), "dir": str(tmp_path / "pipelines")}


def test_each_conditions_leg_runs_the_hourly_resources_in_a_pipeline_of_its_own(store, tmp_path):
    """Production's closures and UA's land in two pipelines, so neither replaces the other's table."""
    production = run_pipeline(
        "conditions_production", store["url"] + "/p", resources=[closures("p1", "p2", count=2)], pipelines_dir=store["dir"]
    )
    ua = run_pipeline("conditions_ua", store["url"] + "/u", resources=[closures("u1", count=1)], pipelines_dir=store["dir"])

    assert production.rows == {"raw_ourhike__closures": 2}
    assert ua.rows == {"raw_ourhike__closures": 1}
    for leg, url in (("conditions_production", "/p"), ("conditions_ua", "/u")):
        pipeline = make_pipeline(leg, store["url"] + url, store["dir"])
        assert pipeline.pipeline_name == f"ourhike_{leg}"
        assert {row["pipeline"] for row in run_log_rows(pipeline)} == {leg}


def test_a_conditions_leg_carries_the_hourly_lane_and_leaves_a_monthly_layer_out(store):
    report = run_pipeline(
        "conditions_ua", store["url"], resources=[closures("u1", count=1), a_monthly_layer()], pipelines_dir=store["dir"]
    )
    assert set(report.verdicts) == {"raw_ourhike__closures"}


def test_raw_store_url_puts_each_leg_under_raw_at_its_own_pipeline_prefix():
    assert raw_store_url("our-hike-raw", "conditions_ua") == "s3://our-hike-raw/raw/dlt/ourhike_conditions_ua"
    assert raw_store_url("our-hike-raw", "conditions_production") == "s3://our-hike-raw/raw/dlt/ourhike_conditions_production"
    assert raw_store_url("our-hike-raw", "monthly") == "s3://our-hike-raw/raw/dlt/ourhike_monthly"


@pytest.mark.parametrize("bucket", ["", "s3://our-hike-raw", "our-hike-raw/raw"])
def test_raw_store_url_refuses_anything_but_a_bare_bucket_name(bucket):
    with pytest.raises(ValueError, match="not a bucket name"):
        raw_store_url(bucket, "conditions_ua")


def test_raw_store_url_refuses_a_lane_that_does_not_exist():
    with pytest.raises(ValueError, match="no lane"):
        raw_store_url("our-hike-raw", "conditions_staging")


def test_only_refuses_a_table_its_lane_does_not_carry():
    with pytest.raises(ValueError, match="raw_testclub__lines: not a table the conditions_ua lane carries"):
        _run.only_tables([closures("u1"), a_monthly_layer()], ["raw_testclub__lines"], "conditions_ua")


def test_the_command_line_loads_the_registry_alone_into_the_warehouse_and_summarises_it(tmp_path):
    """The hourly job's registry step: the monthly lane's sources.json resource, a file in git, and nothing else."""
    warehouse, summary = tmp_path / "warehouse.duckdb", tmp_path / "summary.md"
    _run.main(
        [
            "--lane",
            "monthly",
            "--only",
            "raw_registry__sources",
            "--bucket-url",
            (tmp_path / "registry-store").as_uri(),
            "--pipelines-dir",
            str(tmp_path / "pipelines"),
            "--warehouse",
            str(warehouse),
            "--summary",
            str(summary),
        ]
    )
    with duckdb.connect(str(warehouse), read_only=True) as con:
        tables = {
            name
            for (name,) in con.execute("select table_name from information_schema.tables where table_schema = 'raw'").fetchall()
        }
        (rows,) = con.execute("select count(*) from raw.raw_registry__sources").fetchone()
    assert tables == {"raw_registry__sources", "_extract_runs"}
    assert rows == 1
    text = summary.read_text()
    assert "### Extract: `monthly`" in text and "outcome **loaded**" in text
    assert "| `raw_registry__sources` | stale | 1 | 1 |" in text
    assert "Seconds: sync " in text and "warehouse " in text


def test_a_refused_run_still_writes_its_summary_with_the_reason(store):
    """An empty closures table with no upstream count is refused (the run check), and the summary says so by table."""
    with pytest.raises(ExtractRefused) as refused:
        run_pipeline("conditions_ua", store["url"], resources=[closures()], pipelines_dir=store["dir"])
    text = summary_markdown(refused.value.report, "conditions_ua", failure=refused.value)
    assert "outcome **refused**" in text
    assert "**Refused:**" in text and "raw_ourhike__closures: 0 rows and no upstream count" in text
    assert "| `raw_ourhike__closures` | unknown | 0 |  |" in text


def test_a_run_an_upstream_stops_says_what_stopped_it_and_leaves_its_rows_blank(store):
    """A reader that cannot see its table stops the lane (ConditionsQuery); the summary names the error, and
    writes no row count for a run that never normalized, rather than a zero that reads as "no closures"."""
    with pytest.raises(Exception) as stopped:
        run_pipeline(
            "conditions_ua",
            store["url"],
            resources=[closures(error="permission denied for table closures")],
            pipelines_dir=store["dir"],
        )
    text = summary_markdown(stopped.value.report, "conditions_ua", failure=stopped.value)
    assert "outcome **failed**" in text and "permission denied for table closures" in text
    assert "| `raw_ourhike__closures` | unknown |  |  |" in text


def test_a_summary_with_no_run_says_the_run_never_began():
    text = summary_markdown(None, "conditions_ua", failure=ValueError("no lane 'x'"))
    assert "**Failed before a run began:** `ValueError: no lane 'x'`" in text
