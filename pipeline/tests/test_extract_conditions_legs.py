"""extract/_run.py's conditions legs and its command line, as publish-conditions.yml runs them.

Each leg is the hourly lane for one data environment, in a dlt pipeline of
its own (`LEGS`), so production's and UA's OurHike rows never share a raw
table. A leg isolates each upstream (read_each): one club's failed, slow or
refused read is left out with its last committed table standing, and the
rest load, except OurHike's own Postgres rows, whose failure stops the leg
as it stops today's bake. The command line adds what the workflow's hourly
job needs around a run: the raw bucket's per-leg prefix (`--raw-bucket`),
one table of a lane (`--only`), the committed-file load into the warehouse
(`--warehouse`), and the run's evidence in the job summary (`--summary`),
written on a refused run too. Everything runs against a `file://` raw store
under tmp_path, under conftest.py's socket guard.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import duckdb
import pytest

from extract import _run
from extract._contract import Resource
from extract._kinds import ConditionsQuery
from extract._run import (
    ExtractRefused,
    make_pipeline,
    raw_store_url,
    run_log_rows,
    run_pipeline,
    stops_the_leg,
    summary_markdown,
)
from extract._warehouse import load_warehouse
from lib import http_retry
from lib.freshness_state import Freshness
from tests.test_extract_run import (  # noqa: F401 - `registry` is a fixture
    CLOSURES_URL,
    FIELDS,
    FakeLayer,
    closures,
    feature,
    registry,
)


class Answers:
    """An upstream that answers with the rows it is given and its own count, or fails, or is slow."""

    answer: tuple[dict, ...] = ()
    count: int | None = None
    error: str | None = None
    delay: float = 0.0

    def change_check(self, recorded):
        return Freshness.UNKNOWN, None

    def column_hints(self) -> dict:
        return {"id": {"data_type": "text"}}

    def rows(self, proofs):
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise RuntimeError(self.error)
        if self.count is not None:
            proofs[self.table] = self.count
        yield from (dict(row) for row in self.answer)


@dataclass(frozen=True)
class ClubAnswer(Answers, Resource):
    answer: tuple[dict, ...] = ()
    count: int | None = None
    error: str | None = None
    delay: float = 0.0


@dataclass(frozen=True)
class OurhikeAnswer(Answers, ConditionsQuery):
    """OurHike's own rows: a ConditionsQuery, so its failure stops the leg (stops_the_leg)."""

    answer: tuple[dict, ...] = ()
    count: int | None = None
    error: str | None = None
    delay: float = 0.0


def ourhike_closures(*ids: str, count: int | None = None, error: str | None = None) -> OurhikeAnswer:
    return OurhikeAnswer(
        key="closures", club="ourhike", type="closures", answer=tuple({"id": i} for i in ids), count=count, error=error
    )


def club_closures(club: str, *ids: str, count: int | None = None, error: str | None = None, delay: float = 0.0):
    return ClubAnswer(
        key="closures",
        club=club,
        type="closures",
        answer=tuple({"id": i} for i in ids),
        count=count,
        error=error,
        delay=delay,
    )


def a_monthly_layer() -> ClubAnswer:
    return ClubAnswer(key="lines", club="testclub", type="trail_lines", answer=({"id": "l1"},), count=1)


@pytest.fixture
def store(tmp_path):
    return {"url": (tmp_path / "raw-store").as_uri(), "dir": str(tmp_path / "pipelines")}


def leg(store, *resources, read_seconds=None):
    return run_pipeline(
        "conditions_ua", store["url"], resources=list(resources), pipelines_dir=store["dir"], read_seconds=read_seconds
    )


def warehouse_ids(store) -> dict[str, list[str]]:
    with duckdb.connect() as con:
        load_warehouse(con, make_pipeline("conditions_ua", store["url"], store["dir"]))
        tables = [
            name
            for (name,) in con.execute(
                "select table_name from information_schema.tables where table_schema = 'raw' and table_name <> '_extract_runs'"
            ).fetchall()
        ]
        return {table: sorted(i for (i,) in con.execute(f'select id from raw."{table}"').fetchall()) for table in tables}


def test_each_conditions_leg_runs_the_hourly_resources_in_a_pipeline_of_its_own(store):
    """Production's closures and UA's land in two pipelines, so neither replaces the other's table."""
    production = run_pipeline(
        "conditions_production",
        store["url"] + "/p",
        resources=[ourhike_closures("p1", "p2", count=2)],
        pipelines_dir=store["dir"],
    )
    ua = run_pipeline(
        "conditions_ua", store["url"] + "/u", resources=[ourhike_closures("u1", count=1)], pipelines_dir=store["dir"]
    )

    assert production.rows == {"raw_ourhike__closures": 2}
    assert ua.rows == {"raw_ourhike__closures": 1}
    for name, url in (("conditions_production", "/p"), ("conditions_ua", "/u")):
        pipeline = make_pipeline(name, store["url"] + url, store["dir"])
        assert pipeline.pipeline_name == f"ourhike_{name}"
        assert {row["pipeline"] for row in run_log_rows(pipeline)} == {name}


def test_a_conditions_leg_carries_the_hourly_lane_and_leaves_a_monthly_layer_out(store):
    report = leg(store, ourhike_closures("u1", count=1), a_monthly_layer())
    assert set(report.verdicts) == {"raw_ourhike__closures"}


def test_one_clubs_failed_read_leaves_its_last_table_and_the_other_clubs_closures_still_load(store):
    """The coordinator's case: ATC failing must not hold back NYNJTC. ATC keeps its first run's rows."""
    leg(store, club_closures("atc", "a1", count=1), club_closures("nynjtc", "n1", count=1))

    report = leg(store, club_closures("atc", error="ATC answered 503"), club_closures("nynjtc", "n1", "n2", count=2))

    assert report.outcome == "loaded"
    assert set(report.isolated) == {"raw_atc__closures"}
    assert "ATC answered 503" in report.isolated["raw_atc__closures"]
    assert report.rows == {"raw_nynjtc__closures": 2}
    assert warehouse_ids(store) == {"raw_atc__closures": ["a1"], "raw_nynjtc__closures": ["n1", "n2"]}
    latest = [
        row for row in run_log_rows(make_pipeline("conditions_ua", store["url"], store["dir"])) if row["run_id"] == report.run_id
    ]
    assert {row["table_name"]: row["outcome"] for row in latest} == {
        "raw_atc__closures": "refused",
        "raw_nynjtc__closures": "loaded",
    }


def test_a_club_table_the_run_check_refuses_is_left_out_and_the_rest_load(store):
    """An empty closures answer with no upstream count proves nothing, so that club's last table stands."""
    leg(store, club_closures("atc", "a1", count=1), club_closures("nynjtc", "n1", count=1))

    report = leg(store, club_closures("atc"), club_closures("nynjtc", "n3", count=1))

    assert set(report.isolated) == {"raw_atc__closures"}
    assert "0 rows and no upstream count" in report.isolated["raw_atc__closures"]
    assert warehouse_ids(store) == {"raw_atc__closures": ["a1"], "raw_nynjtc__closures": ["n3"]}


def test_a_club_closures_read_with_no_upstream_count_is_left_out_and_its_last_table_stands(store):
    leg(store, club_closures("atc", "a1", "a2", count=2), club_closures("nynjtc", "n1", count=1))

    report = leg(store, club_closures("atc", "a1"), club_closures("nynjtc", "n1", count=1))

    assert set(report.isolated) == {"raw_atc__closures"}
    assert "1 rows and no upstream count" in report.isolated["raw_atc__closures"]
    assert warehouse_ids(store) == {"raw_atc__closures": ["a1", "a2"], "raw_nynjtc__closures": ["n1"]}


@pytest.mark.parametrize(
    "atc",
    [club_closures("atc", error="ATC answered 503"), club_closures("atc")],
    ids=["its read failed", "the run check refused its unproven zero"],
)
def test_a_club_refused_on_its_first_ever_run_is_an_empty_table_in_the_warehouse_not_a_missing_one(store, atc):
    """int_closures__unioned refs every club's raw table, so a missing one fails every club's closures in dbt."""
    report = leg(store, atc, club_closures("nynjtc", "n1", count=1))

    assert set(report.isolated) == {"raw_atc__closures"}
    assert warehouse_ids(store) == {"raw_atc__closures": [], "raw_nynjtc__closures": ["n1"]}


def test_a_club_whose_first_run_was_refused_and_whose_second_loaded_is_read_from_the_second(store):
    leg(store, club_closures("atc", error="ATC answered 503"), club_closures("nynjtc", "n1", count=1))

    leg(store, club_closures("atc", "a1", count=1), club_closures("nynjtc", "n1", count=1))

    assert warehouse_ids(store) == {"raw_atc__closures": ["a1"], "raw_nynjtc__closures": ["n1"]}


def test_a_whole_leg_refused_on_its_first_run_creates_no_empty_tables_for_a_later_build(store):
    """OurHike's own rows stop the leg; an empty raw_ourhike__closures would publish as "no OurHike closures"."""
    with pytest.raises(ExtractRefused):
        leg(store, ourhike_closures(), club_closures("nynjtc", "n1", count=1))

    assert warehouse_ids(store) == {}


@pytest.mark.usefixtures("registry")
def test_an_arcgis_field_retyped_upstream_refuses_that_layer_only_and_the_rest_load(store, requests_mock):
    """dlt's `data_type: freeze` contract raises at extract, which runs every resource of the leg at once."""
    layer = FakeLayer(requests_mock, CLOSURES_URL, [feature(10, "Bridge out")])
    leg(store, closures(), club_closures("nynjtc", "n1", count=1))
    retyped = [dict(field, type="esriFieldTypeInteger") if field["name"] == "NAME" else field for field in FIELDS]
    first_metadata = layer.metadata

    def metadata(request, context):
        answer = first_metadata(request, context)
        return answer if answer is None else {**answer, "fields": retyped}

    requests_mock.get(CLOSURES_URL, json=metadata)
    layer.etag, layer.features = "v2", [feature(10, 7)]

    report = leg(store, closures(), club_closures("nynjtc", "n1", "n2", count=2), read_seconds=60)

    assert set(report.isolated) == {"raw_testclub__closures_layer"}
    assert "contract" in report.isolated["raw_testclub__closures_layer"]
    assert report.rows == {"raw_nynjtc__closures": 2}
    with duckdb.connect() as con:
        counts = load_warehouse(con, make_pipeline("conditions_ua", store["url"], store["dir"]))
    assert counts == {"raw_nynjtc__closures": 2, "raw_testclub__closures_layer": 1}, "the layer's first-run row stands"
    again = leg(store, closures(), club_closures("nynjtc", "n1", "n2", count=2), read_seconds=60)
    assert again.verdicts["raw_testclub__closures_layer"] != "fresh", "the refused layer advanced no marker"


@pytest.mark.usefixtures("registry")
def test_an_arcgis_layer_whose_metadata_stops_answering_mid_read_refuses_that_layer_only(store, requests_mock, monkeypatch):
    """column_hints() asks for the metadata a third time; outside read_each(), a 503 there stopped the whole leg."""
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)
    layer = FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    leg(store, closures(), club_closures("nynjtc", "n1", count=1))
    asked = {"n": 0}
    first_metadata = layer.metadata

    def metadata(request, context):
        asked["n"] += 1
        if asked["n"] >= 3:  # the change check and one more answer; every request after them fails
            context.status_code = 503
            return {"error": "busy"}
        return first_metadata(request, context)

    requests_mock.get(CLOSURES_URL, json=metadata)
    layer.etag, layer.features = "v2", [feature(10), feature(11)]

    report = leg(store, closures(), club_closures("nynjtc", "n1", "n2", count=2), read_seconds=60)

    assert set(report.isolated) == {"raw_testclub__closures_layer"}
    assert report.rows == {"raw_nynjtc__closures": 2}


def test_a_slow_club_is_left_out_when_the_read_budget_runs_out_and_nothing_waits_for_it(store):
    """A host behind a 10-second Crawl-delay is never hurried to fit: its read is abandoned, not shortened."""
    started = time.monotonic()
    report = leg(store, club_closures("atc", "a1", count=1, delay=5.0), club_closures("nynjtc", "n1", count=1), read_seconds=0.5)
    assert time.monotonic() - started < 4.5
    assert set(report.isolated) == {"raw_atc__closures"}
    assert "TimeoutError: no answer within the leg's 0.5 s read budget" in report.isolated["raw_atc__closures"]
    assert report.rows == {"raw_nynjtc__closures": 1}


def test_ourhikes_own_rows_still_stop_the_whole_leg_when_their_read_fails(store):
    """export_conditions.py publishes nothing when it cannot read the database, and a phone keeps its last file
    with its true age; carrying the last table forward under a new `generated_at` would outrun its source."""
    assert stops_the_leg(ourhike_closures())
    assert not stops_the_leg(club_closures("atc"))
    with pytest.raises(RuntimeError, match="permission denied"):
        leg(store, ourhike_closures(error="permission denied for table closures"), club_closures("nynjtc", "n1", count=1))


def test_ourhikes_own_rows_refused_by_the_run_check_refuse_the_whole_leg(store):
    with pytest.raises(ExtractRefused, match="raw_ourhike__closures: 0 rows and no upstream count"):
        leg(store, ourhike_closures(), club_closures("nynjtc", "n1", count=1))


def test_the_hourly_lane_still_refuses_the_whole_run_on_one_refusal(store):
    """Isolation is the legs' alone: fixture mode and the lane tests run `hourly`, where one refusal refuses all."""
    with pytest.raises(ExtractRefused):
        run_pipeline(
            "hourly",
            store["url"],
            resources=[club_closures("atc"), club_closures("nynjtc", "n1", count=1)],
            pipelines_dir=store["dir"],
        )


def test_raw_store_url_puts_each_lane_and_leg_under_raw_at_the_prefix_elt_md_names():
    assert raw_store_url("our-hike-raw", "conditions_ua") == "s3://our-hike-raw/raw/dlt/conditions_ua"
    assert raw_store_url("our-hike-raw", "conditions_production") == "s3://our-hike-raw/raw/dlt/conditions_production"
    assert raw_store_url("our-hike-raw", "monthly") == "s3://our-hike-raw/raw/dlt/monthly"


@pytest.mark.parametrize("bucket", ["", "s3://our-hike-raw", "our-hike-raw/raw"])
def test_raw_store_url_refuses_anything_but_a_bare_bucket_name(bucket):
    with pytest.raises(ValueError, match="not a bucket name"):
        raw_store_url(bucket, "conditions_ua")


def test_raw_store_url_refuses_a_lane_that_does_not_exist():
    with pytest.raises(ValueError, match="no lane"):
        raw_store_url("our-hike-raw", "conditions_staging")


def test_only_refuses_a_table_its_lane_does_not_carry():
    with pytest.raises(ValueError, match="raw_testclub__lines: not a table the conditions_ua lane carries"):
        _run.only_tables([ourhike_closures("u1"), a_monthly_layer()], ["raw_testclub__lines"], "conditions_ua")


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
    """An empty OurHike closures table with no upstream count refuses the leg, and the summary says why, by table."""
    with pytest.raises(ExtractRefused) as refused:
        leg(store, ourhike_closures())
    text = summary_markdown(refused.value.report, "conditions_ua", failure=refused.value)
    assert "outcome **refused**" in text
    assert "**Refused:**" in text and "raw_ourhike__closures: 0 rows and no upstream count" in text
    assert "| `raw_ourhike__closures` | unknown | 0 |  |" in text


def test_a_summary_names_each_club_refused_on_its_own_and_says_its_last_table_stands(store):
    leg(store, club_closures("atc", "a1", count=1), club_closures("nynjtc", "n1", count=1))
    report = leg(store, club_closures("atc", error="ATC answered 503"), club_closures("nynjtc", "n1", count=1))
    text = summary_markdown(report, "conditions_ua")
    assert "**Refused on its own**" in text and "ATC answered 503" in text
    assert "| `raw_atc__closures` | unknown | refused, last table stands |  |" in text
    assert "| `raw_nynjtc__closures` | unknown | 1 | 1 |" in text


def test_a_run_ourhikes_reader_stops_says_what_stopped_it_and_leaves_its_rows_blank(store):
    """The summary names the error, and writes no row count for a run that never normalized, rather than a zero
    that reads as "no closures"."""
    with pytest.raises(RuntimeError) as stopped:
        leg(store, ourhike_closures(error="permission denied for table closures"))
    text = summary_markdown(stopped.value.report, "conditions_ua", failure=stopped.value)
    assert "outcome **failed**" in text and "permission denied for table closures" in text
    assert "| `raw_ourhike__closures` | unknown |  |  |" in text


def test_a_summary_with_no_run_says_the_run_never_began():
    text = summary_markdown(None, "conditions_ua", failure=ValueError("no lane 'x'"))
    assert "**Failed before a run began:** `ValueError: no lane 'x'`" in text
