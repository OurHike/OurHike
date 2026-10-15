"""_answers: keep what a conditions leg's extract received from NWS and from OurHike's Postgres, for the hour's comparison.

    python -m extract._run --lane conditions_ua ... --record-answers data/hourly_parity/answers
    python -m extract._fixtures --raw-dir R --warehouse W --record-answers DIR

pipeline/ELT.md's open question 17, answered by the maintainer's poll of
2026-10-10, "Compare every soak hour": every hour, today's exporters run on
the same upstream answers the dbt writers' build read, and parity.py compares
the two sides' files (hourly_parity.py). Each upstream is asked once, by the
extract, and this module keeps the answers it got, so today's exporters are
served them afterwards and nobody's server is asked a second time.

WHAT IS KEPT, AND WHY ONLY THIS. Three answers, each read in full on every
run of a conditions leg, so the answer this run kept is the input of the
table the build read whenever that table loaded this run:
- NWS's `/alerts/active` body (RECORDED_URLS), which NwsAlerts reads every
  run because the endpoint answers no conditional request (its docstring);
- the rows of export_conditions.py's PUBLIC_CLOSURES_SQL and
  PUBLIC_REPORTS_SQL (RECORDED_QUERIES), which ConditionsQuery reads every run
  because its change check is never FRESH.
The other conditions inputs are not this run's answers, and nothing here
keeps them: ATC's reviewed file and the work projects are files in git, the
same bytes on both sides; ATC's pages are read and NYNJTC's posts landed
only when they move (NYNJTC's terms once a day), so the table a build reads
is usually an earlier run's. hourly_parity.py says what each of those compares on.

ONLY THE TRANSPORT IS WRAPPED, as fixture mode swaps only the transport
(extract/_fixtures.py): every session _kinds.session() makes has each of its
mounted adapters wrapped in _RecordingAdapter, which sends the request it is
given, unchanged, and keeps the answer when the URL is one RECORDED_URLS names;
and _kinds.psycopg is wrapped so that the cursor that runs one of
RECORDED_QUERIES' texts keeps the rows it fetched. No request is added,
repeated or altered, so robots.txt, USER_AGENT and every Crawl-delay are the
session's own, exactly as without this module.

THE FILES ARE FIXTURE MODE'S, so today's exporters read them as they read the
fixtures (parity.py --answers-dir): `conditions/nws_alerts.json` holds the body
as received, byte for byte, and `conditions/ourhike_postgres.json` is
FixtureConnection's document, each query's columns with their Postgres type
names and its rows in the order the query returned them, a timestamp written
in isoformat() and read back by FixtureConnection as the datetime psycopg
gave. A value of any type FixtureConnection cannot give back as psycopg gave
it (a date, a Decimal, a UUID) refuses that query's recording, by name, rather
than handing today's exporter a different type: the backend's closures and
reports columns are varchar, text, float8, json and timestamp
(backend/app/models/closure.py and report.py, read 2026-10-10), so none is
expected. `answers.json` beside them says what was kept, from which URL or
query, and what this run did with each table (table_states()).

PEOPLE. The two queries select no person column: export_conditions.py's text
leaves them in the database, and ConditionsQuery.rows() refuses a row set
naming WITHHELD_COLUMNS before anything is returned, so before anything is
kept. NWS's property names match none of _kinds.py's person rules (Reasoned:
NWS_TEXT_PROPERTIES and NWS_JSON_PROPERTIES against PERSON_FIELDS and
PERSON_SHAPED, 2026-10-10). The recording stays on the runner, and reaches the
comparison only through the leg's private history store (hand_off.py
put-bundle), never as an Actions artifact, which anyone could download from a
public repository.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests

from extract import _kinds
from lib.nws_alerts import ALERTS_URL as NWS_ALERTS_URL

#: What answers.json says it is, so a reader refuses another file of the same name.
FORMAT = "ourhike-recorded-answers/1"
ANSWERS_FILE = "answers.json"
#: The URLs whose answers are kept, without their query, each with the raw table its answer lands in.
RECORDED_URLS = {NWS_ALERTS_URL: "raw_nws__alerts"}
#: The export_conditions.py artifacts whose query rows are kept (_kinds.CONDITIONS_QUERIES' keys), each with its table.
RECORDED_QUERIES = {"closures": "raw_ourhike__closures", "reports": "raw_ourhike__reports"}


class Unrecordable(ValueError):
    """A value FixtureConnection could not give back as psycopg gave it."""


def _base(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _recorded_value(value, type_name: str):
    """`value` as JSON can hold it and FixtureConnection gives it back: unchanged, or a timestamp's isoformat()."""
    from extract._fixtures import TIMESTAMP_TYPES

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, dict | list):
        json.dumps(value)  # a json column's value is JSON already; anything else in it raises TypeError here
        return value
    if isinstance(value, datetime) and type_name in TIMESTAMP_TYPES:
        return value.isoformat()
    raise Unrecordable(f"a {type(value).__name__} in a {type_name} column, which FixtureConnection would not give back")


class Recorder:
    """The answers one run kept: HTTP answers by exact URL, query rows by RECORDED_QUERIES key. Thread-safe, because a
    leg asks its upstreams one folder per thread (extract/_run.py's by_folder())."""

    def __init__(self):
        self._lock = threading.Lock()
        self.http: dict[str, dict] = {}
        self.postgres: dict[str, dict] = {}
        self.refused: dict[str, str] = {}
        self._queries = {sql.strip(): key for key, (_table, sql) in _kinds.CONDITIONS_QUERIES.items() if key in RECORDED_QUERIES}

    def wants(self, url: str) -> bool:
        return _base(url) in RECORDED_URLS

    def query_key(self, sql) -> str | None:
        return self._queries.get(sql.strip()) if isinstance(sql, str) else None

    def keep_http(self, request, response: requests.Response) -> None:
        """The answer to `request`, the last one for its URL: a retried request keeps the answer the resource used."""
        body = response.content
        kept = {
            "url": request.url,
            "table": RECORDED_URLS[_base(request.url)],
            "status": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "body": body,
            "sha256": hashlib.sha256(body).hexdigest(),
            "received_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        with self._lock:
            self.http[request.url] = kept

    def keep_rows(self, key: str, description, types, rows: list) -> None:
        """One query's rows, as FixtureConnection's document holds them; a value it could not give back refuses the query."""

        def type_name(column) -> str:
            info = types.get(column.type_code) if types is not None else None
            return str(getattr(info, "name", None) or column.type_code)

        columns = [[column.name, type_name(column)] for column in description or []]
        try:
            kept_rows = [
                {
                    name: _recorded_value(row[name] if isinstance(row, dict) else row[index], kind)
                    for index, (name, kind) in enumerate(columns)
                }
                for row in rows
            ]
        except (Unrecordable, TypeError, ValueError) as unrecordable:
            with self._lock:
                self.postgres.pop(key, None)
                self.refused[key] = str(unrecordable)
            return
        with self._lock:
            self.refused.pop(key, None)
            self.postgres[key] = {"table": RECORDED_QUERIES[key], "columns": columns, "rows": kept_rows}

    def write(self, directory: Path, states: dict[str, str], *, lane: str, run_id: str | None, outcome: str) -> Path:
        """The files the module docstring names, under `directory`; returns answers.json's path."""
        from extract._fixtures import CONDITIONS_DIR, NWS_FIXTURE, POSTGRES_FIXTURE

        conditions = directory / CONDITIONS_DIR
        conditions.mkdir(parents=True, exist_ok=True)
        with self._lock:
            http, postgres, refused = dict(self.http), dict(self.postgres), dict(self.refused)
        files = {RECORDED_URLS[NWS_ALERTS_URL]: f"{CONDITIONS_DIR}/{NWS_FIXTURE}"}
        answers: dict[str, dict] = {}
        for url, kept in sorted(http.items()):
            name = files[kept["table"]]
            (directory / name).write_bytes(kept["body"])
            answers[url] = {key: value for key, value in kept.items() if key != "body"} | {
                "file": name,
                "bytes": len(kept["body"]),
            }
        if postgres:
            document = {key: {"columns": kept["columns"], "rows": kept["rows"]} for key, kept in sorted(postgres.items())}
            (conditions / POSTGRES_FIXTURE).write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        queries = {
            key: {"table": kept["table"], "rows": len(kept["rows"]), "file": f"{CONDITIONS_DIR}/{POSTGRES_FIXTURE}"}
            for key, kept in sorted(postgres.items())
        }
        descriptor = {
            "format": FORMAT,
            "lane": lane,
            "run_id": run_id,
            "outcome": outcome,
            "written_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "http": answers,
            "postgres": queries,
            "refused": refused,
            "tables": dict(sorted(states.items())),
        }
        path = directory / ANSWERS_FILE
        path.write_text(json.dumps(descriptor, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return path


def table_states(report) -> dict[str, str]:
    """What a run did with each table it planned, from its RunReport: `loaded` (read this run and committed), `kept`
    (FRESH: its last committed table stands, unchanged upstream), `refused` (left out on its own; its last committed
    table stands), `incomplete` (ran out of budget; its last committed table stands), `waiting` (never loaded, not
    taken on), `withdrawn` (unavailable) or `not loaded` (the run committed nothing). A table the run did not plan, a
    daily one not yet due, is absent: its last committed table stands."""
    states: dict[str, str] = {}
    for name, verdict in (report.verdicts or {}).items():
        if name in report.isolated:
            states[name] = "refused"
        elif name in report.incomplete:
            states[name] = "incomplete"
        elif name in report.waiting:
            states[name] = "waiting"
        elif verdict == "fresh":
            states[name] = "kept"
        elif verdict == "unavailable":
            states[name] = "withdrawn"
        elif report.load_id is not None:
            states[name] = "loaded"
        else:
            states[name] = "not loaded"
    return states


class _RecordingAdapter(requests.adapters.BaseAdapter):
    """Sends each request through the adapter it wraps, unchanged, and hands the recorder an answer it wants."""

    def __init__(self, inner: requests.adapters.BaseAdapter, recorder: Recorder):
        super().__init__()
        self.inner, self.recorder = inner, recorder

    def send(self, request, **kwargs):
        response = self.inner.send(request, **kwargs)
        if self.recorder.wants(request.url):
            self.recorder.keep_http(request, response)
        return response

    def close(self):
        self.inner.close()


class _RecordingCursor:
    """A cursor that keeps the rows a RECORDED_QUERIES query fetched, and is otherwise the cursor it wraps."""

    def __init__(self, inner, recorder: Recorder, connection):
        self._inner, self._recorder, self._connection = inner, recorder, connection
        self._key: str | None = None

    def __enter__(self):
        self._inner.__enter__()
        return self

    def __exit__(self, *exc):
        return self._inner.__exit__(*exc)

    def execute(self, query, *args, **kwargs):
        self._key = self._recorder.query_key(query)
        self._inner.execute(query, *args, **kwargs)
        return self

    def fetchall(self):
        rows = self._inner.fetchall()
        if self._key is not None:
            adapters = getattr(self._connection, "adapters", None)
            self._recorder.keep_rows(self._key, self._inner.description, getattr(adapters, "types", None), rows)
        return rows

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _RecordingConnection:
    """A connection whose cursors are _RecordingCursor; everything else is the connection it wraps."""

    def __init__(self, inner, recorder: Recorder):
        self._inner, self._recorder = inner, recorder

    def __enter__(self):
        self._inner.__enter__()
        return self

    def __exit__(self, *exc):
        return self._inner.__exit__(*exc)

    def cursor(self, *args, **kwargs):
        return _RecordingCursor(self._inner.cursor(*args, **kwargs), self._recorder, self._inner)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _RecordingPsycopg:
    """Stands in for the psycopg module (or fixture mode's FixturePsycopg) inside extract/_kinds.py while a run records."""

    def __init__(self, inner, recorder: Recorder):
        self._inner, self._recorder = inner, recorder

    def connect(self, *args, **kwargs):
        return _RecordingConnection(self._inner.connect(*args, **kwargs), self._recorder)

    def __getattr__(self, name):
        return getattr(self._inner, name)


@contextmanager
def recording(recorder: Recorder) -> Iterator[Recorder]:
    """Keep what `recorder` wants of every answer the extract receives until the block ends, then put the transport
    back as it was. Wraps whatever transport is in place, so fixture mode's records what fixture mode served."""
    real_session, real_psycopg = _kinds.session, _kinds.psycopg

    def recording_session(entry: dict | None = None) -> requests.Session:
        http = real_session(entry)
        for prefix, adapter in list(http.adapters.items()):
            http.mount(prefix, _RecordingAdapter(adapter, recorder))
        return http

    _kinds.session = recording_session
    _kinds.psycopg = _RecordingPsycopg(real_psycopg, recorder)
    try:
        yield recorder
    finally:
        _kinds.session, _kinds.psycopg = real_session, real_psycopg
