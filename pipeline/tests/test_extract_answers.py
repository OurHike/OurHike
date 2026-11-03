"""extract/_answers.py: a conditions leg keeps the answers it received from NWS and OurHike's Postgres, byte for byte.

The transport under the recorder is fixture mode's (extract/_fixtures.py's FixtureAdapter and FixturePsycopg), the
same stand-ins every extract test uses for a server, so what is asserted is that the recorder hands the resource the
answer the transport gave, unchanged, and keeps that same answer in fixture mode's own files, which today's exporters
then read back (hourly_parity.py). requests_mock is not used: it replaces Session.get_adapter, which no mounted
adapter, the recorder's included, would then see.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import pytest
import requests

import export_conditions
import make_dbt_fixtures
from extract import _answers, _fixtures, _kinds, _run
from extract._contract import all_resources, discover, discover_shared
from extract._kinds import ConditionsQuery, NwsAlerts
from extract._run import RunReport
from lib.nws_alerts import ALERTS_URL as NWS_ALERTS_URL


def _nws() -> NwsAlerts:
    return NwsAlerts(key="alerts", club="nws", type="warnings")


def _query(key: str) -> ConditionsQuery:
    return ConditionsQuery(key=key, club="ourhike", type="closures" if key == "closures" else "warnings")


@pytest.fixture
def served(monkeypatch):
    """Fixture mode's transport, as extract/_fixtures.py's build() installs it: NWS's body and OurHike's Postgres."""
    body = make_dbt_fixtures._nws_alerts()
    postgres = make_dbt_fixtures._ourhike_postgres()
    adapter = _fixtures.FixtureAdapter({}, {}, {}, nws=body)

    def fixture_session(entry=None):
        http = requests.Session()
        http.mount("https://", adapter)
        return http

    monkeypatch.setattr(_kinds, "session", fixture_session)
    monkeypatch.setattr(_kinds, "psycopg", _fixtures.FixturePsycopg(postgres))
    monkeypatch.setenv(export_conditions.URL_ENV_VAR, "postgresql://fixture-mode.invalid/none")
    return body, postgres


def test_the_recorder_keeps_nws_body_byte_for_byte_and_hands_the_resource_the_same_answer(served, tmp_path):
    body, _ = served
    unrecorded = list(_nws().rows({}))

    recorder = _answers.Recorder()
    with _answers.recording(recorder):
        recorded = list(_nws().rows({}))
    recorder.write(tmp_path, {"raw_nws__alerts": "loaded"}, lane="conditions_ua", run_id="r1", outcome="loaded")

    assert recorded == unrecorded, "the resource reads exactly what it reads without the recorder"
    kept = (tmp_path / "conditions" / "nws_alerts.json").read_bytes()
    assert kept == json.dumps(body).encode(), "the body FixtureAdapter served, byte for byte"
    answers = json.loads((tmp_path / _answers.ANSWERS_FILE).read_text())
    assert answers["http"][NWS_ALERTS_URL]["table"] == "raw_nws__alerts"
    assert answers["http"][NWS_ALERTS_URL]["status"] == 200 and answers["http"][NWS_ALERTS_URL]["bytes"] == len(kept)
    assert answers["format"] == _answers.FORMAT and answers["tables"] == {"raw_nws__alerts": "loaded"}


def test_a_url_the_recorder_does_not_name_is_sent_and_answered_as_before_and_not_kept(monkeypatch):
    other = "https://example.org/arcgis/rest/services/closures/FeatureServer/0"
    adapter = _fixtures.FixtureAdapter({other: [{"type": "Feature", "properties": {"OBJECTID": 1}, "geometry": None}]}, {}, {})

    def fixture_session(entry=None):
        http = requests.Session()
        http.mount("https://", adapter)
        return http

    monkeypatch.setattr(_kinds, "session", fixture_session)
    recorder = _answers.Recorder()
    with _answers.recording(recorder):
        answered = _kinds.session().get(other, params={"f": "json"}, timeout=5)

    assert answered.status_code == 200 and answered.json()["objectIdField"] == "OBJECTID"
    assert recorder.http == {} and recorder.postgres == {}


def test_the_recorder_keeps_closures_and_reports_rows_as_fixture_connection_gives_them_back(served, tmp_path):
    _, postgres = served
    recorder = _answers.Recorder()
    with _answers.recording(recorder):
        for key in ("closures", "reports", "notes"):
            _query(key).change_check(None)
            list(_query(key).rows({}))
    recorder.write(tmp_path, {}, lane="conditions_ua", run_id="r1", outcome="loaded")

    document = json.loads((tmp_path / "conditions" / _fixtures.POSTGRES_FIXTURE).read_text())
    assert sorted(document) == ["closures", "reports"], "RECORDED_QUERIES alone: notes and disputes feed no family"
    for key in ("closures", "reports"):
        assert document[key] == {"columns": postgres[key]["columns"], "rows": postgres[key]["rows"]}
        # Read back as export_conditions.py's read_<key>() reads it, through FixtureConnection: the same rows, the
        # timestamps datetimes again, as psycopg handed them to the extract.
        description, rows = _fixtures.FixtureConnection(document).answer(_kinds.CONDITIONS_QUERIES[key][1])
        assert [column.name for column in description] == [name for name, _ in postgres[key]["columns"]]
        assert rows == [_fixtures.FixtureConnection._row(postgres[key], row) for row in postgres[key]["rows"]]
    assert isinstance(rows[0]["timestamp"], datetime)


def test_a_value_fixture_connection_could_not_give_back_refuses_that_querys_recording_by_name():
    recorder = _answers.Recorder()
    description = [type("Column", (), {"name": "mile", "type_code": "numeric"})()]

    recorder.keep_rows("closures", description, None, [{"mile": Decimal("476.6")}])

    assert recorder.postgres == {}
    assert "Decimal in a numeric column" in recorder.refused["closures"]


def test_recording_puts_the_transport_back_even_when_the_run_raises(served):
    before = (_kinds.session, _kinds.psycopg)
    with pytest.raises(RuntimeError), _answers.recording(_answers.Recorder()):
        assert _kinds.session is not before[0] and _kinds.psycopg is not before[1]
        raise RuntimeError("the leg stopped")
    assert (_kinds.session, _kinds.psycopg) == before


def test_table_states_says_what_a_run_did_with_each_table_it_planned():
    report = RunReport(run_id="r", lane="conditions_ua", outcome="loaded", load_id="1760.1")
    report.verdicts = {
        "raw_nws__alerts": "unknown",
        "raw_atc__atc_updates": "fresh",
        "raw_atc__atc_trail_updates_pages": "stale",
        "raw_nysparks__oprhp_trail_closures": "unknown",
        "raw_ourhike__notes": "unavailable",
    }
    report.isolated = {"raw_nysparks__oprhp_trail_closures": "timed out"}
    report.incomplete = {"raw_atc__atc_trail_updates_pages": "read 4 of 6 pages"}

    assert _answers.table_states(report) == {
        "raw_nws__alerts": "loaded",
        "raw_atc__atc_updates": "kept",
        "raw_atc__atc_trail_updates_pages": "incomplete",
        "raw_nysparks__oprhp_trail_closures": "refused",
        "raw_ourhike__notes": "withdrawn",
    }


def _leg_arguments(tmp_path) -> list[str]:
    return [
        "--lane",
        "conditions_ua",
        "--bucket-url",
        (tmp_path / "raw-store").as_uri(),
        "--pipelines-dir",
        str(tmp_path / "pipelines"),
        *("--only", "raw_nws__alerts", "--only", "raw_ourhike__closures", "--only", "raw_ourhike__reports"),
        "--record-answers",
        str(tmp_path / "answers"),
    ]


def test_a_conditions_legs_run_keeps_the_answers_its_load_was_made_from_and_says_what_it_did(served, tmp_path):
    """extract/_run.py's main(), as publish-conditions.yml's extract step runs it with --record-answers."""
    body, postgres = served

    report = _run.main(_leg_arguments(tmp_path))

    answers = tmp_path / "answers"
    descriptor = json.loads((answers / _answers.ANSWERS_FILE).read_text())
    assert report.outcome == "loaded"
    assert (descriptor["lane"], descriptor["run_id"], descriptor["outcome"]) == ("conditions_ua", report.run_id, "loaded")
    assert descriptor["tables"] == {
        table: "loaded" for table in ("raw_nws__alerts", "raw_ourhike__closures", "raw_ourhike__reports")
    }
    assert json.loads((answers / "conditions" / "nws_alerts.json").read_text()) == body
    kept = json.loads((answers / "conditions" / _fixtures.POSTGRES_FIXTURE).read_text())
    assert {key: kept[key]["rows"] for key in kept} == {key: postgres[key]["rows"] for key in ("closures", "reports")}


def test_answers_that_cannot_be_written_leave_the_runs_own_outcome_alone(served, tmp_path, monkeypatch, capsys):
    def refuses(*args, **kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr(_answers.Recorder, "write", refuses)

    report = _run.main(_leg_arguments(tmp_path))

    assert report.outcome == "loaded" and not report.isolated
    assert "::warning title=Answers not kept::OSError: no space left on device" in capsys.readouterr().out


def test_the_recorded_tables_are_the_tables_the_conditions_resources_land():
    tables = {resource.table for resource in all_resources(discover() + discover_shared())}
    assert set(_answers.RECORDED_URLS.values()) | set(_answers.RECORDED_QUERIES.values()) <= tables
    assert _nws().table == _answers.RECORDED_URLS[NWS_ALERTS_URL]
    assert {key: _query(key).table for key in _answers.RECORDED_QUERIES} == _answers.RECORDED_QUERIES
