"""hourly_parity: the six conditions files against today's exporters, on the hour's own answers, every soak hour.

    python hourly_parity.py bundle --answers DIR --warehouse W --processed P --out B
    python hourly_parity.py compare --bundle B --out R [--summary FILE] [--extract-python PY]
        [--run BUILD_RUN --attempt N --commit SHA --leg ua --compared-in RUN]

pipeline/ELT.md's open question 17, answered by the maintainer's poll of
2026-10-10, "Compare every soak hour": the six `conditions/*` keys block go
because their parity families (parity.py) compared only on the fixture
warehouse, and these are the files that put a hiker in front of something
dangerous. So every hour that publish-conditions.yml builds them, today's
exporters run on the same upstream answers as the dbt writers, and parity.py
compares the two, family by family. gate_report.py --hourly-dir reads the
results (HOURLY_FORMAT), and stops counting a key as blocking once they are
clean across the soak (gate_report.soak_coverage()).

TWO HALVES, on two runners. `bundle` runs in publish-conditions.yml's
hand-off step, before the build's warehouse is handed to its checks, and
gathers, from that runner, everything today's exporters need into one
directory, in fixture mode's layout under `raw/` so parity.py's old sides
read it as they read the fixtures (parity.py --answers-dir), and the six
files the writers wrote under `new/`. hand_off.py put-bundle sends it to the
leg's private history store, and check-conditions.yml's `parity` job, which
the same dispatch starts beside the checks, takes it back and runs
`compare`. Not in the publish job: what it has left after its publish goes
to the warehouse's hand-off and the freshness step
(.github/tests/test_conditions_build_budget.py), no job of
publish-conditions.yml may run long without keeping publish-data held
(check-conditions.yml's header says why), and the build's warehouse,
3,055,300,608 bytes on soak run 676 (1,112,305,570 gzipped, handed off in
71.90 s; its log, 2026-10-15), is far more than a comparison of six files
needs, so only what they read crosses.

WHAT EACH FAMILY COMPARES ON (FAMILIES' `compared_on`). Each upstream is asked
once, by the extract. Three answers are read whole every hour and recorded as
received (extract/_answers.py): NWS's alerts, and OurHike's closures and
reports, the moderated query a conditions leg already reads on its own
database every hour, so `reports` compares on real data. For the other three
no hour's answers can feed today's exporter, and each says why:
- `atc_updates`: today's fetcher walks ATC's listing pages, which the extract
  never requests (it reads the sitemap, ELT.md's CL11), and re-reads every
  update page a day old, where the extract reads only the pages that moved. So
  it compares on the page rows the build read, as fetch_atc_updates.py's cache
  (`raw/atc_updates.json`): lib/atc_scrape.py's parse_update() output, the
  same function on both sides, minus the prose, which neither gate reads.
- `nynjtc_alerts`: the extract reads NYNJTC's posts only when their
  (id, modified_gmt) set moves and the place terms once a day; soak run 624
  read neither (its log, 2026-10-10). So it compares on the posts and terms
  the build read, rebuilt into the WordPress answers parse_alert() and
  parse_terms() read (`raw/conditions/nynjtc_trail_alerts.json`).
- `work_projects` and ATC's reviewed rows: files in git, the same bytes on
  both sides at this commit, compared only when the hour's extract loaded the
  table from this checkout or kept it because its sha256 had not moved
  (`tables`, extract/_answers.table_states()).
What the landed-row families leave untested is dlt's landing of those
answers, which both sides then share: tests/test_extract_*.py and the run
check hold that, and their fixture families still compare the fetchers.

A FAMILY NOT COMPARED THIS HOUR SAYS WHY, and is never a difference: its
input was not this hour's (NWS's read was refused, so the table the build read
is an earlier hour's, whose answer was not recorded), the build held its
writer back (decision 81: the key kept the bucket's last copy), or no bundle
reached the job. Only a difference nothing explains, or a comparison that
crashed, turns the run red; gate_report.py counts every hour that compared
nothing as a hole in the soak.

A COMPARISON THAT STOPS PART WAY IS RECORDED, NEVER ABSENT. `compare` writes
run.json before the first family, and again before and after each, renamed
into place whole so a kill mid-write leaves the last whole copy, with
`finished` false until the last answer is in. A step its cap stops ends as a
failure, and the runner signals its shell, SIGINT, then SIGTERM 7.5 s later,
then kills the process tree 2.5 s after that, which runs no handler
(actions/runner's StepsRunner.cs and ProcessInvoker.cs, read 2026-10-15).
Whatever of that reaches this process, or a compare() that raised, the
run.json on disk is a whole one in which the family being compared reads
`failed` (STOPPED_IN: a crash, which gate_report.py reads as `differs`) and
those after it `not_compared` (NOT_REACHED: a hole), and the parity job
uploads it, as it uploads a failed step's results. Until the 2026-10-15
adversarial review (finding S2-3) run.json was written once, after the last
family, so such an hour left none, and gate_report.py read it as a run that
never came, which decision 158's 2.5-hour rule absorbs. That is how the gate
tells the two apart: an hour whose `hourly_parity.py compare` began has a
run.json, a take that failed or timed out included (check-conditions.yml
runs the compare step after it, and every family reads not compared); an
hour with none is one whose build was never dispatched, or whose parity job
was cancelled, lost its runner or had no Python before that command began,
and only those fall under decision 158.

NO RECORD AND NO PERSON FIELD IS PRINTED OR UPLOADED. parity.py runs with
--keys-only, so its console and its result files carry each difference's key
and changed field paths, never either side's record; this file prints counts,
keys and reasons. The bundle holds records (OurHike's reports among them),
so it moves only through the private history store, never as an artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
#: What `compare` writes as `run.json` beside the families' results; gate_report.py reads nothing else as one.
HOURLY_FORMAT = "ourhike-hourly-parity/1"
#: What `bundle` writes as `bundle.json`.
BUNDLE_FORMAT = "ourhike-hourly-parity-bundle/1"
BUNDLE_FILE = "bundle.json"
RUN_FILE = "run.json"
RESULTS_DIR = "results"
RAW = "raw"
NEW = "new"
#: extract/_answers.py's directory layout, which is fixture mode's (extract/_fixtures.py's CONDITIONS_DIR and files).
ANSWERS_FILE = "answers.json"
ATC_CACHE = "atc_updates.json"
NYNJTC_ANSWERS = "conditions/nynjtc_trail_alerts.json"
NWS_ANSWER = "conditions/nws_alerts.json"
POSTGRES_ANSWERS = "conditions/ourhike_postgres.json"
SQUARES = "weather/squares.json"
#: build_marts.py's BUILD_RECORD and its exits that mean part of the build was held back (PARTIAL_EXIT and
#: DEGRADED_PARTIAL_EXIT), written out rather than imported: build_marts.py imports dbt's world, and this runs on
#: the extract's venv in the hand-off step.
BUILD_RECORD = "build_marts.build_record"
HELD_BACK_EXITS = (5, 6)
#: A comparison that has not answered in this long is stopped and reads `failed`. @unvalidated, picked: far above the
#: fixtures' slowest family (atc_updates, 0.9 s; the six took 3.4 s together, Measured 2026-10-10 in a shared 4-core
#: sandbox) and inside the compare step's 3 minutes for one slow family. The summary's seconds column on the first
#: real runs settles it.
FAMILY_SECONDS = 120

#: gate_report.py's SOAK_HOURS and SOAK_MAX_GAP_HOURS, which the summary's not-compared line names: written out,
#: because gate_report.py imports this file, and held equal by tests/test_hourly_parity.py. check-conditions.yml's
#: MAX_AGE_HOURS is the second (decision 200).
GATE_SOAK_HOURS = 72
GATE_SOAK_MAX_GAP_HOURS = 2.5

#: A table's state (extract/_answers.table_states()) that leaves the committed table equal to this checkout's file:
#: read from it this hour, or kept because its sha256 had not moved since the load that read it.
FROM_THIS_CHECKOUT = ("loaded", "kept")


@dataclass(frozen=True)
class HourlyFamily:
    name: str  # parity.py's family
    key: str  # the R2 key the file publishes as
    new_file: str  # the pub_ writer's `location`, under data/processed/dbt/
    compared_on: str  # what both sides read this hour, in a few words for the summary
    # closures and reports: FixtureConnection's module imports dlt, which requirements.txt does not pin, so their old
    # sides run on the extract's venv, as CI's parity step runs them (pipeline-tests.yml).
    extract_venv: bool = False


FAMILIES: dict[str, HourlyFamily] = {
    family.name: family
    for family in (
        HourlyFamily(
            "closures",
            "conditions/closures.json",
            "conditions_closures.json",
            "recorded answers: OurHike's Postgres rows for PUBLIC_CLOSURES_SQL, this hour",
            extract_venv=True,
        ),
        HourlyFamily(
            "reports",
            "conditions/reports.json",
            "conditions_reports.json",
            "recorded answers: OurHike's Postgres rows for PUBLIC_REPORTS_SQL, this hour",
            extract_venv=True,
        ),
        HourlyFamily(
            "weather_alerts",
            "conditions/weather_alerts.json",
            "conditions_weather_alerts.json",
            "recorded answer: NWS's /alerts/active body, this hour, on the weather squares the build read",
        ),
        HourlyFamily(
            "atc_updates",
            "conditions/atc_updates.json",
            "conditions_atc_updates.json",
            "reference/atc_updates.json at this commit, and the ATC page rows the build read (no listing page is recorded)",
        ),
        HourlyFamily(
            "nynjtc_alerts",
            "conditions/nynjtc_alerts.json",
            "conditions_nynjtc_alerts.json",
            "the NYNJTC posts and place terms the build read (read only when they move, so not this hour's answers)",
        ),
        HourlyFamily(
            "work_projects",
            "conditions/work_projects.json",
            "conditions_work_projects.json",
            "reference/work_projects.json at this commit, on both sides",
        ),
    )
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# --- bundle: on the publish job's runner, after the hand-off ------------------------------------------------------


def _json_value(value):
    """A JSON column read back from DuckDB: its text parsed, or the value as it came."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _columns(con, table: str) -> dict[str, str] | None:
    """{column: DuckDB type} of `schema.table`, or None when the warehouse has no such table."""
    schema, name = table.split(".", 1)
    rows = con.execute(
        "select column_name, data_type from information_schema.columns where table_schema = ? and table_name = ?", [schema, name]
    ).fetchall()
    return {column: kind for column, kind in rows} if rows else None


def _stamp_sql(column: str, kind: str) -> str:
    """`column` as WordPress wrote it, `YYYY-MM-DDTHH:MM:SS`, where dlt landed it as a timestamp; as written otherwise."""
    if kind.upper().startswith("TIMESTAMP"):
        return f"strftime({column}, '%Y-%m-%dT%H:%M:%S')"
    return f"cast({column} as varchar)"


def atc_cache(con) -> tuple[dict, str]:
    """fetch_atc_updates.py's cache, from the page rows the build read: (document, what it holds).

    Each landed row is lib/atc_scrape.py's parse_update() output for one update the sitemap lists, so every row is
    `listed`; `text` is empty, because the prose never lands (ELT.md's CL11) and export_atc_updates.py's gate reads
    none of it (automatic_rows(), auto_row())."""
    table = "raw.raw_atc__atc_trail_updates_pages"
    columns = _columns(con, table)
    if columns is None:
        return {"fetched_at": _now(), "listed": 0, "updates": {}}, f"{table} is not in the warehouse: no ATC page this hour"
    order = "_row" if "_row" in columns else "slug"
    rows = con.execute(
        f"select slug, title, category, states, date_modified, date_published, miles from {table} order by {order}"
    ).fetchall()
    updates = {}
    for slug, title, category, states, modified, published, miles in rows:
        updates[slug] = {
            "slug": slug,
            "title": title,
            "category": category,
            "states": _json_value(states) or [],
            "date_modified": modified,
            "date_published": published,
            "miles": _json_value(miles) or [],
            "text": "",
            "listed": True,
        }
    return {"fetched_at": _now(), "listed": len(updates), "updates": updates}, f"{len(updates)} page rows from {table}"


def nynjtc_answers(con) -> tuple[dict | None, str]:
    """The WordPress answers parity.py's _nynjtc_alerts_old() reads, from the posts and terms the build read.

    Only what parse_alert() and parse_terms() read: a post's id, slug, link, `title` (`{"rendered": ...}`, landed as
    JSON), `modified` and `date` (landed as timestamps, read back as WordPress wrote them, which carries no offset and
    no fraction), its categories and its four place-term lists (landed as JSON). `content` stays out: no published
    field reads it (lib/nynjtc_alerts.py's PUBLISHED_FIELDS), and nothing here is a place to keep NYNJTC's writing."""
    from lib.nynjtc_alerts import PLACE_TAXONOMIES, TRAIL_ALERTS_CATEGORY_ID

    posts_table, terms_table = "raw.raw_nynjtc__nynjtc_trail_alerts", "raw.raw_nynjtc__nynjtc_trail_alerts_terms"
    posts_columns, terms_columns = _columns(con, posts_table), _columns(con, terms_table)
    if posts_columns is None or terms_columns is None:
        missing = [table for table, columns in ((posts_table, posts_columns), (terms_table, terms_columns)) if columns is None]
        return None, f"{' and '.join(missing)} not in the warehouse"
    con.execute("set TimeZone = 'UTC'")
    stamps = {name: _stamp_sql(name, posts_columns[name]) for name in ("modified", "date") if name in posts_columns}
    lists = [name for name in ("categories", *PLACE_TAXONOMIES) if name in posts_columns]
    selected = ["id", "slug", "link", "title", *(f"{sql} as {name}" for name, sql in stamps.items()), *lists]
    order = "date desc, id desc" if "date" in posts_columns else "id desc"
    rows = con.execute(f"select {', '.join(selected)} from {posts_table} order by {order}").fetchall()
    names = ["id", "slug", "link", "title", *stamps, *lists]
    posts = []
    for row in rows:
        post = dict(zip(names, row, strict=True))
        post["title"] = _json_value(post["title"])
        for name in lists:
            post[name] = _json_value(post[name])
        if "categories" not in post:
            # The extract asks for the Trail Alerts category alone (WordpressPosts.scope()), so every landed post is in it.
            post["categories"] = [TRAIL_ALERTS_CATEGORY_ID]
        posts.append(post)
    terms: dict[str, list] = {taxonomy: [] for taxonomy in PLACE_TAXONOMIES}
    for taxonomy, term_id, name, slug in con.execute(
        f"select taxonomy, id, name, slug from {terms_table} order by taxonomy, id"
    ).fetchall():
        terms.setdefault(taxonomy, []).append({"id": term_id, "name": name, "slug": slug})
    counted = ", ".join(f"{len(listed)} {taxonomy}" for taxonomy, listed in terms.items())
    return {"posts": posts, "terms": terms}, f"{len(posts)} posts and {counted} terms"


def weather_squares(con) -> tuple[str | None, str]:
    """The squares document the build placed alerts on (derived.weather_squares, which step_weather_squares.py lands
    whole), as its text, or None when this build had none."""
    if _columns(con, "derived.weather_squares") is None:
        return None, "derived.weather_squares is not in the warehouse: the build ran without the squares this hour"
    (text,) = con.execute("select document_json from derived.weather_squares").fetchone()
    return text, "derived.weather_squares, as the build read it"


def build_record(con) -> dict | None:
    """build_marts.py's record of the build (its BUILD_RECORD), or None when the warehouse holds none."""
    if _columns(con, BUILD_RECORD) is None:
        return None
    (text,) = con.execute(f"select record from {BUILD_RECORD}").fetchone()
    return json.loads(text)


def bundle(answers: Path, warehouse: Path, processed: Path, out: Path) -> dict:
    """Everything `compare` needs, under `out`; returns bundle.json's document. Never raises for a part it cannot
    gather: that part is named in the document with why, and `compare` says the family it feeds was not compared."""
    import duckdb

    if out.exists():
        shutil.rmtree(out)
    raw, new = out / RAW, out / NEW
    raw.mkdir(parents=True)
    new.mkdir(parents=True)
    document: dict = {"format": BUNDLE_FORMAT, "prepared_at": _now(), "inputs": {}, "writer_files": {}}

    descriptor = answers / ANSWERS_FILE
    if descriptor.exists():
        document["answers"] = json.loads(descriptor.read_text(encoding="utf-8"))
        for name in (NWS_ANSWER, POSTGRES_ANSWERS):
            if (answers / name).exists():
                (raw / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(answers / name, raw / name)
    else:
        document["answers"] = None
        document["inputs"]["answers"] = f"no {descriptor}: the extract kept no answers this hour"

    def gather(name: str, read) -> None:
        try:
            value, said = read()
        except Exception as failed:  # noqa: BLE001 - one part's failure is that family's, said, never the bundle's
            document["inputs"][name] = f"not gathered: {type(failed).__name__}: {failed}"
            return
        document["inputs"][name] = said
        if value is None:
            return
        path = raw / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding="utf-8")

    try:
        con = duckdb.connect(str(warehouse), read_only=True)
    except Exception as failed:  # noqa: BLE001
        document["inputs"]["warehouse"] = f"not read: {type(failed).__name__}: {failed}"
        con = None
    if con is not None:
        with con:
            gather(ATC_CACHE, lambda: atc_cache(con))
            gather(NYNJTC_ANSWERS, lambda: nynjtc_answers(con))
            gather(SQUARES, lambda: weather_squares(con))
            try:
                document["build"] = build_record(con)
            except Exception as failed:  # noqa: BLE001
                document["build"] = None
                document["inputs"]["build record"] = f"not read: {type(failed).__name__}: {failed}"
    for family in FAMILIES.values():
        written = processed / family.new_file
        if written.exists():
            shutil.copyfile(written, new / family.new_file)
            document["writer_files"][family.new_file] = written.stat().st_size
        else:
            document["writer_files"][family.new_file] = None
    (out / BUNDLE_FILE).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return document


# --- compare: on the parity job's runner ---------------------------------------------------------------------------


@dataclass
class FamilyAnswer:
    key: str
    verdict: str  # equal, no_records, differs, not_compared, failed
    compared_on: str
    why: str | None = None
    outcome: str | None = None  # parity.py's, when it ran
    old_records: int | None = None
    new_records: int | None = None
    differences: int = 0
    explained: int = 0
    seconds: float | None = None
    result: str | None = None  # the result file, relative to the comparison's directory


#: The verdicts that turn the run red: a difference nothing explains, and a comparison that crashed, which is a
#: defect in the comparison until somebody reads why.
RED = ("differs", "failed")

#: What run.json says of a family compare() has not reached, and of the one it is comparing, until each answer is in:
#: what a run.json left by a step killed at its cap, or by a compare() that raised, then says (the module docstring,
#: "A COMPARISON THAT STOPS PART WAY").
NOT_REACHED = "the comparison stopped before it reached this family (its step was killed or timed out, or compare() raised)"
STOPPED_IN = (
    "the comparison stopped while it compared this family (its step was killed or timed out, or compare() raised) "
    "before parity.py's answer was recorded"
)


def _write_run(out: Path, run: dict) -> None:
    """`out/run.json`, replaced whole: written beside it, then renamed over it, so a kill mid-write leaves the last
    whole one."""
    partial = out / f".{RUN_FILE}.partial"
    partial.write_text(json.dumps(run, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(partial, out / RUN_FILE)


def why_not(family: HourlyFamily, document: dict, bundle_dir: Path) -> str | None:
    """Why `family` cannot be compared on this bundle this hour, or None when it can."""
    answers = document.get("answers") or {}
    tables = answers.get("tables") or {}
    raw = bundle_dir / RAW

    def state(table: str) -> str:
        return tables.get(table, "not planned by this hour's extract")

    if family.name in ("closures", "reports"):
        table = f"raw_ourhike__{family.name}"
        if family.name in (answers.get("refused") or {}):
            return f"its rows were not recorded: {answers['refused'][family.name]}"
        if family.name not in (answers.get("postgres") or {}):
            return "no rows for its query were recorded this hour"
        if state(table) != "loaded":
            return f"{table} was {state(table)} this hour, so the build read an earlier hour's rows, which were not recorded"
    elif family.name == "weather_alerts":
        kept = [kept for kept in (answers.get("http") or {}).values() if kept.get("table") == "raw_nws__alerts"]
        if not kept:
            return "no NWS answer was recorded this hour"
        if kept[-1].get("status") != 200:
            return f"NWS answered {kept[-1].get('status')} this hour"
        if state("raw_nws__alerts") != "loaded":
            return f"raw_nws__alerts was {state('raw_nws__alerts')} this hour, so the build read an earlier hour's alerts"
        if not (raw / SQUARES).exists():
            return f"no weather squares: {document['inputs'].get(SQUARES, 'none were gathered')}"
    elif family.name == "atc_updates":
        for table in ("raw_atc__atc_updates", "raw_atc__atc_trail_updates"):
            if state(table) not in FROM_THIS_CHECKOUT:
                return f"{table} was {state(table)} this hour, so the build may have read another copy of the reviewed file"
        if not (raw / ATC_CACHE).exists():
            return f"no page rows: {document['inputs'].get(ATC_CACHE, 'none were gathered')}"
    elif family.name == "nynjtc_alerts":
        if not (raw / NYNJTC_ANSWERS).exists():
            return f"no posts or terms: {document['inputs'].get(NYNJTC_ANSWERS, 'none were gathered')}"
    elif family.name == "work_projects":
        if state("raw_ourhike__work_projects") not in FROM_THIS_CHECKOUT:
            return (
                f"raw_ourhike__work_projects was {state('raw_ourhike__work_projects')} this hour, so the build may have read "
                "another copy of the reviewed file"
            )
    if not (bundle_dir / NEW / family.new_file).exists() and (document.get("build") or {}).get("exit") in HELD_BACK_EXITS:
        return (
            f"the build held part of itself back (exit {(document.get('build') or {}).get('exit')}, decision 81) and its writer "
            f"wrote no {family.new_file}, so {family.key} kept the bucket's last copy this hour"
        )
    return None


def judge(family: HourlyFamily, result: dict, new_written: bool) -> tuple[str, str | None]:
    """(verdict, why) for one parity.py result file."""
    outcome = result.get("outcome")
    if outcome == "no_differences":
        if not result.get("old_records") and not result.get("new_records"):
            return "no_records", "both files hold no record this hour, so only their top-level fields were compared"
        return "equal", None
    if outcome in ("differences", "one_side_writes"):
        return "differs", result.get("message") or f"{len(result.get('differences') or [])} difference(s) nothing explains"
    if outcome == "old_side_refused":
        if new_written:
            return "differs", f"today's exporter refused this hour's input ({result.get('message')}), and the writer wrote a file"
        return "not_compared", f"neither side wrote a file: today's exporter refused this hour's input ({result.get('message')})"
    if outcome == "neither_writes":
        return "not_compared", "neither today's exporter nor the writer wrote a file this hour"
    return "failed", f"parity.py answered an outcome this file does not know: {outcome!r}"


def run_family(family: HourlyFamily, bundle_dir: Path, out: Path, python: str) -> FamilyAnswer:
    """parity.py for one family, keys only, on the bundle; its answer."""
    answer = FamilyAnswer(key=family.key, verdict="failed", compared_on=family.compared_on)
    results = out / RESULTS_DIR
    results.mkdir(parents=True, exist_ok=True)
    (results / f"{family.name}.json").unlink(missing_ok=True)
    new_file = bundle_dir / NEW / family.new_file
    command = [python, str(PIPELINE_DIR / "parity.py"), family.name, "--new", str(new_file)]
    command += ["--answers-dir", str(bundle_dir / RAW), "--json-dir", str(results), "--keys-only"]
    started = time.monotonic()
    try:
        finished = subprocess.run(command, cwd=PIPELINE_DIR, capture_output=True, text=True, timeout=FAMILY_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        answer.seconds = round(time.monotonic() - started, 1)
        answer.why = f"parity.py did not answer within {FAMILY_SECONDS} s"
        return answer
    answer.seconds = round(time.monotonic() - started, 1)
    # --keys-only: the console names keys and changed fields, never a record (parity.without_records()).
    for line in finished.stdout.splitlines():
        print(f"  {family.name}: {line}")
    path = results / f"{family.name}.json"
    if not path.exists():
        # The exception's type alone: its message could carry a record's value, and this log is public.
        last = (finished.stderr.strip().splitlines() or [""])[-1]
        answer.why = f"parity.py exited {finished.returncode} without a result ({last.split(':', 1)[0] or 'no message'})"
        return answer
    result = json.loads(path.read_text(encoding="utf-8"))
    answer.verdict, answer.why = judge(family, result, new_file.exists())
    answer.outcome = result.get("outcome")
    answer.old_records, answer.new_records = result.get("old_records"), result.get("new_records")
    answer.differences = len(result.get("differences") or [])
    answer.explained = len(result.get("explained") or [])
    answer.result = f"{RESULTS_DIR}/{family.name}.json"
    return answer


def compare(
    bundle_dir: Path,
    out: Path,
    *,
    python: str = sys.executable,
    extract_python: str | None = None,
    identity: dict | None = None,
    missing: str | None = None,
) -> dict:
    """Every family's answer on `bundle_dir`, written as `out/run.json` (HOURLY_FORMAT); returns that document.

    `missing` says why there is no bundle to compare, and every family then reads not compared. run.json is written
    before the first family and again before and after each, with `finished` false until the last answer is in (the
    module docstring, "A COMPARISON THAT STOPS PART WAY")."""
    out.mkdir(parents=True, exist_ok=True)
    document = {}
    if missing is None:
        try:
            document = json.loads((bundle_dir / BUNDLE_FILE).read_text(encoding="utf-8"))
            if document.get("format") != BUNDLE_FORMAT:
                missing = f"{bundle_dir / BUNDLE_FILE} is format {document.get('format')!r}, not {BUNDLE_FORMAT}"
        except (OSError, ValueError) as unreadable:
            missing = f"{bundle_dir / BUNDLE_FILE} could not be read ({type(unreadable).__name__})"
    started = time.monotonic()
    build = document.get("build") or {}
    run = {
        "format": HOURLY_FORMAT,
        **(identity or {}),
        "built_at": build.get("started_at"),
        "build_exit": build.get("exit"),
        "bundle": "taken" if missing is None else f"missing: {missing}",
        "inputs": document.get("inputs") or {},
    }
    answers = {
        family.name: FamilyAnswer(family.key, "not_compared", family.compared_on, why=NOT_REACHED) for family in FAMILIES.values()
    }

    def record(finished: bool) -> dict:
        run.update(
            compared_at=_now(),
            seconds=round(time.monotonic() - started, 1),
            finished=finished,
            families={name: asdict(answer) for name, answer in answers.items()},
        )
        _write_run(out, run)
        return run

    record(False)
    for family in FAMILIES.values():
        if missing is not None:
            answers[family.name] = FamilyAnswer(family.key, "not_compared", family.compared_on, why=f"no bundle: {missing}")
            continue
        answers[family.name] = FamilyAnswer(family.key, "failed", family.compared_on, why=STOPPED_IN)
        record(False)
        if reason := why_not(family, document, bundle_dir):
            answers[family.name] = FamilyAnswer(family.key, "not_compared", family.compared_on, why=reason)
        else:
            chosen = (extract_python or python) if family.extract_venv else python
            answers[family.name] = run_family(family, bundle_dir, out, chosen)
        record(False)
    return record(True)


def run_label(run: dict) -> str:
    """The build run a comparison is of, as `<run id>` or `<run id>.<attempt>` when its attempt is known."""
    return f"{run.get('run')}" + (f".{run['attempt']}" if run.get("attempt") else "")


VERDICT_WORDS = {
    "equal": "equal",
    "no_records": "equal, no records",
    "differs": "**differs**",
    "not_compared": "not compared",
    "failed": "**comparison failed**",
}


def not_compared_headline(run: dict) -> str | None:
    """The line that leads the summary when any file was not compared, or None when every one was.

    A file not compared leaves this step green by design (the docstring's "A FAMILY NOT COMPARED THIS HOUR SAYS WHY"),
    the job going red only once the store has had no bundle for SOAK_MAX_GAP_HOURS (decision 200, check-conditions.yml),
    and gate_report.py's soak_coverage() then counts that key clean only once a whole SOAK_HOURS of runs after it have
    compared it clean. All eight soak runs from 666 (2026-10-14 18:07 UTC) to 676 put no bundle, nor did 5 of the 18
    runs of 2026-10-11 that had the step to put one, so none of their hours compared anything; and the summary said so
    only in its reasons and a closing "0 file(s) turn this run red" (review finding S2-1 of PR #1805 — dlt → dbt
    re-platform as one go/no-go change), so this line comes first."""
    families = run["families"]
    missing = [answer for answer in families.values() if answer["verdict"] == "not_compared"]
    if not missing:
        return None
    reasons = sorted({str(answer["why"]) for answer in missing})
    why = f" Why: {reasons[0]}" if len(reasons) == 1 else " Each one's reason is listed below the table."
    if len(missing) == len(families):
        said = f"**Nothing was compared this hour: none of the {len(families)} files.**"
    else:
        said = f"**{len(missing)} of the {len(families)} files were not compared this hour.**"
    return (
        f"{said} On its own an hour like this is a warning, and the job goes red only once the leg's store has had no "
        f"bundle for {GATE_SOAK_MAX_GAP_HOURS:g} hours (decision 200); but gate_report.py clears a key only when every "
        f"run of the soak's last {GATE_SOAK_HOURS} hours compared it clean, so this hour holds each of these keys back "
        f"for {GATE_SOAK_HOURS} hours.{why}"
    )


def summary_markdown(run: dict) -> str:
    """The run's answer, family by family with counts, for $GITHUB_STEP_SUMMARY: counts, keys and reasons, no record."""
    families = run["families"]
    headline = not_compared_headline(run)
    unseen = sum(answer["verdict"] == "not_compared" for answer in families.values())
    lines = [
        f"### The six conditions files against today's exporters, {run.get('leg') or 'this'} leg (hourly_parity.py)",
        "",
        *([headline, ""] if headline else []),
        f"Build run {run_label(run)} on `{str(run.get('commit') or '')[:12]}`, build started {run.get('built_at') or 'unknown'}, "
        f"compared in {run.get('seconds')} s. Each file that build published from its dbt writer, against today's exporter "
        "on the same answers, by parity.py with --keys-only.",
        "",
        "| File | Answer | Records, today / dbt | Unexplained / explained differences | Compared on | Seconds |",
        "|---|---|---|---|---|---|",
    ]
    for answer in families.values():
        records = "" if answer["old_records"] is None else f"{answer['old_records']} / {answer['new_records']}"
        counted = "" if answer["outcome"] is None else f"{answer['differences']} / {answer['explained']}"
        seconds = "" if answer["seconds"] is None else answer["seconds"]
        lines.append(
            f"| `{answer['key']}` | {VERDICT_WORDS[answer['verdict']]} | {records} | {counted} | {answer['compared_on']} | {seconds} |"
        )
    reasons = [(answer["key"], answer["why"]) for answer in families.values() if answer["why"]]
    if reasons:
        lines += ["", *[f"- `{key}`: {why}" for key, why in reasons]]
    red = [answer["key"] for answer in families.values() if answer["verdict"] in RED]
    lines += [
        "",
        f"**{len(red)} file(s) turn this run red**: "
        + (", ".join(f"`{key}`" for key in red) if red else "none")
        + (f"; **{unseen} not compared**" if unseen else "")
        + ". The per-family results, keys and changed fields only, are this job's "
        + f"`hourly-parity-{run.get('leg') or '<leg>'}` artifact"
        + (f" in run {run['compared_in']}" if run.get("compared_in") else "")
        + "; gate_report.py --hourly-dir reads them.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    gathering = commands.add_parser("bundle", help="gather what today's exporters need, on the publish job's runner")
    gathering.add_argument("--answers", type=Path, required=True, help="the extract's --record-answers directory")
    gathering.add_argument("--warehouse", type=Path, required=True, help="the build's warehouse")
    gathering.add_argument("--processed", type=Path, required=True, help="where the writers wrote, data/processed/dbt")
    gathering.add_argument("--out", type=Path, required=True)
    comparing = commands.add_parser("compare", help="compare the six files, family by family, on a bundle")
    comparing.add_argument("--bundle", type=Path, required=True)
    comparing.add_argument("--out", type=Path, required=True, help="where run.json and results/<family>.json are written")
    comparing.add_argument("--summary", type=Path, help="a file the answer is appended to, $GITHUB_STEP_SUMMARY")
    comparing.add_argument("--extract-python", help="the extract venv's python, for closures and reports")
    comparing.add_argument("--missing", help="why there is no bundle: every family then reads not compared")
    comparing.add_argument("--run", help="the publish-conditions.yml run whose build this compares (its build_run)")
    comparing.add_argument("--attempt", help="that run's attempt, when known")
    comparing.add_argument("--commit", help="the commit that build ran on, which take-bundle held this checkout to")
    comparing.add_argument("--leg", help="the leg, ua or production")
    comparing.add_argument("--compared-in", help="the run this comparison ran in, whose artifact holds its results")
    args = parser.parse_args(argv)
    if args.command == "bundle":
        document = bundle(args.answers, args.warehouse, args.processed, args.out)
        written = sum(size is not None for size in document["writer_files"].values())
        for name, said in sorted(document["inputs"].items()):
            print(f"hourly_parity: {name}: {said}")
        print(f"hourly_parity: bundled {written} writer file(s) and the hour's inputs into {args.out}")
        return 0
    identity = {
        "run": args.run,
        "attempt": args.attempt,
        "commit": args.commit,
        "leg": args.leg,
        "compared_in": args.compared_in,
    }
    run = compare(args.bundle, args.out, extract_python=args.extract_python, identity=identity, missing=args.missing)
    text = summary_markdown(run)
    if args.summary is not None:
        with args.summary.open("a", encoding="utf-8") as page:
            page.write(text)
    headline = not_compared_headline(run)
    if headline and all(answer["verdict"] == "not_compared" for answer in run["families"].values()):
        # One annotation for the whole hour, ahead of the six, so the run's annotations open on it.
        print(f"::warning title=Nothing compared this hour::{headline.replace('**', '')}")
    for answer in run["families"].values():
        line = f"{answer['key']}: {answer['verdict']}" + (f" ({answer['why']})" if answer["why"] else "")
        if answer["verdict"] in RED:
            print(f"::error title={answer['key']} against today's exporter::{line}")
        elif answer["verdict"] == "not_compared":
            print(f"::warning title={answer['key']} not compared this hour::{line}")
        else:
            print(f"hourly_parity: {line}")
    return 1 if any(answer["verdict"] in RED for answer in run["families"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
