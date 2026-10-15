"""hourly_parity.py: the hour's comparison of the six conditions files with today's exporters, on one bundle.

The bundle's landed-row halves are held here to the shapes dlt lands (a NYNJTC post's `modified` a timestamp with time
zone, its title and place lists JSON text, an ATC page's states and miles JSON text: read off the fixture warehouse's
columns, 2026-10-10), on small warehouses written by hand; the whole path,
record and serve included, runs over the fixture warehouse in the session that built it (pipeline/ELT.md, "The hourly
lanes", says what it measured). parity.py itself is run as a subprocess, as the parity job runs it.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

import export_atc_updates
import hourly_parity
import parity
from lib.nynjtc_alerts import TRAIL_ALERTS_CATEGORY_ID, parse_alert, parse_terms

PAGE = {
    "slug": "harpers-ferry-footbridge-closure",
    "title": "Harpers Ferry Footbridge Closure",
    "category": "Detour",
    "states": ["WV", "MD"],
    "date_modified": "2026-09-20T10:00:00-04:00",
    "date_published": "2026-09-01T09:00:00-04:00",
    "miles": [{"direction": "NOBO", "start": 1025.6, "end": 1026.1, "raw": "1,025.6 - 1,026.1"}],
}
POST = {
    "id": 4101,
    "slug": "ramapo-dunderberg-reroute",
    "link": "https://www.nynjtc.org/news/ramapo-dunderberg-reroute",
    "title": {"rendered": "Ramapo&#8211;Dunderberg Reroute"},
    "modified": "2026-06-16T10:22:33",
    "date": "2026-06-01T08:00:00",
    "categories": [TRAIL_ALERTS_CATEGORY_ID],
    "trail": [45],
    "park": [101],
    "region": [],
    "state": [3],
}
TERMS = [
    ("trail", 45, "Ramapo-Dunderberg Trail", "ramapo-dunderberg-trail"),
    ("park", 101, "Harriman State Park", "harriman"),
    ("state", 3, "New York", "ny"),
]


def _warehouse(path: Path, *, pages=True, nynjtc=True, squares=True, build_exit: int | None = 0) -> Path:
    """A warehouse holding what the bundle reads, in the types dlt lands them as."""
    with duckdb.connect(str(path)) as con:
        for schema in ("raw", "derived", "build_marts"):
            con.execute(f"create schema {schema}")
        if pages:
            con.execute(
                "create table raw.raw_atc__atc_trail_updates_pages (slug varchar, title varchar, category varchar, states varchar, "
                "date_modified varchar, date_published varchar, miles varchar, source_url varchar, _row bigint)"
            )
            con.execute(
                "insert into raw.raw_atc__atc_trail_updates_pages values (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                [PAGE["slug"], PAGE["title"], PAGE["category"], json.dumps(PAGE["states"]), PAGE["date_modified"]]
                + [
                    PAGE["date_published"],
                    json.dumps(PAGE["miles"]),
                    f"https://appalachiantrail.org/trail-updates/{PAGE['slug']}/",
                ],
            )
        if nynjtc:
            con.execute("set TimeZone = 'America/New_York'")  # a runner's zone must not move a stamp
            con.execute(
                "create table raw.raw_nynjtc__nynjtc_trail_alerts (id bigint, slug varchar, link varchar, title varchar, "
                "modified timestamp with time zone, date timestamp with time zone, categories varchar, trail varchar, park varchar, "
                "region varchar, state varchar, content varchar)"
            )
            con.execute(
                "insert into raw.raw_nynjtc__nynjtc_trail_alerts values (?, ?, ?, ?, ?::timestamptz, ?::timestamptz, ?, ?, ?, ?, ?, ?)",
                [POST["id"], POST["slug"], POST["link"], json.dumps(POST["title"]), POST["modified"] + "+00:00"]
                + [POST["date"] + "+00:00", json.dumps(POST["categories"]), json.dumps(POST["trail"]), json.dumps(POST["park"])]
                + [json.dumps(POST["region"]), json.dumps(POST["state"]), json.dumps({"rendered": "NYNJTC's own words"})],
            )
            con.execute(
                "create table raw.raw_nynjtc__nynjtc_trail_alerts_terms (taxonomy varchar, id bigint, name varchar, slug varchar)"
            )
            con.executemany("insert into raw.raw_nynjtc__nynjtc_trail_alerts_terms values (?, ?, ?, ?)", TERMS)
        if squares:
            con.execute("create table derived.weather_squares (release varchar, document_json varchar)")
            con.execute("insert into derived.weather_squares values ('r1', ?)", [json.dumps({"release": "r1", "zones": {}})])
        if build_exit is not None:
            con.execute("create table build_marts.build_record (format integer, record varchar)")
            record = {"exit": build_exit, "started_at": "2026-10-10 18:21:42"}
            con.execute("insert into build_marts.build_record values (1, ?)", [json.dumps(record)])
    return path


def _answers(folder: Path, tables: dict[str, str] | None = None, *, nws_status: int = 200) -> Path:
    """What extract/_answers.py writes after a conditions leg's run."""
    (folder / "conditions").mkdir(parents=True, exist_ok=True)
    (folder / "conditions" / "nws_alerts.json").write_text('{"type": "FeatureCollection", "features": []}')
    (folder / "conditions" / "ourhike_postgres.json").write_text(json.dumps({"closures": {"columns": [], "rows": []}}))
    states = {
        table: "loaded"
        for table in (
            "raw_nws__alerts",
            "raw_ourhike__closures",
            "raw_ourhike__reports",
            "raw_atc__atc_updates",
            "raw_atc__atc_trail_updates",
            "raw_ourhike__work_projects",
        )
    }
    descriptor = {
        "format": "ourhike-recorded-answers/1",
        "http": {"https://api.weather.gov/alerts/active": {"table": "raw_nws__alerts", "status": nws_status}},
        "postgres": {key: {"table": f"raw_ourhike__{key}", "rows": 0} for key in ("closures", "reports")},
        "refused": {},
        "tables": {**states, **(tables or {})},
    }
    (folder / "answers.json").write_text(json.dumps(descriptor))
    return folder


def _processed(folder: Path, names=None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for family in hourly_parity.FAMILIES.values():
        if names is None or family.new_file in names:
            (folder / family.new_file).write_text(json.dumps({"generated_at": "2026-10-10T18:22:00Z"}))
    return folder


def test_the_bundle_rebuilds_fetch_atc_updates_cache_from_the_page_rows_the_build_read(tmp_path):
    out = tmp_path / "bundle"
    hourly_parity.bundle(_answers(tmp_path / "answers"), _warehouse(tmp_path / "w.duckdb"), _processed(tmp_path / "p"), out)

    (update,) = export_atc_updates.cached_updates(out / "raw" / hourly_parity.ATC_CACHE)
    assert (update.slug, update.title, update.category, update.states) == (
        PAGE["slug"],
        PAGE["title"],
        PAGE["category"],
        PAGE["states"],
    )
    assert (update.date_modified, update.date_published) == (PAGE["date_modified"], PAGE["date_published"])
    assert [(m.direction, m.start, m.end, m.raw) for m in update.miles] == [("NOBO", 1025.6, 1026.1, "1,025.6 - 1,026.1")]
    assert update.text == "", "ATC's prose never lands, and neither gate reads it"


def test_the_bundle_rebuilds_nynjtc_posts_as_wordpress_wrote_them_whatever_the_runners_time_zone(tmp_path):
    out = tmp_path / "bundle"
    hourly_parity.bundle(_answers(tmp_path / "answers"), _warehouse(tmp_path / "w.duckdb"), _processed(tmp_path / "p"), out)

    answers = json.loads((out / "raw" / hourly_parity.NYNJTC_ANSWERS).read_text())
    (post,) = answers["posts"]
    assert post == POST, "every field parse_alert() reads, as WordPress served it"
    assert "content" not in post, "NYNJTC's own words are not carried"
    vocabularies = {taxonomy: parse_terms(terms) for taxonomy, terms in answers["terms"].items()}
    alert = parse_alert(post, vocabularies)
    assert (alert.modified_at, alert.title) == ("2026-06-16T10:22:33", "Ramapo–Dunderberg Reroute")
    assert [term.name for term in alert.place_terms] == ["Ramapo-Dunderberg Trail", "Harriman State Park"]


def test_the_bundle_carries_the_recorded_answers_the_squares_the_writer_files_and_the_build_exit(tmp_path):
    out = tmp_path / "bundle"
    document = hourly_parity.bundle(
        _answers(tmp_path / "answers"), _warehouse(tmp_path / "w.duckdb", build_exit=5), _processed(tmp_path / "p"), out
    )

    assert (out / "raw" / "conditions" / "nws_alerts.json").read_text() == '{"type": "FeatureCollection", "features": []}'
    assert json.loads((out / "raw" / hourly_parity.SQUARES).read_text()) == {"release": "r1", "zones": {}}
    assert sorted(path.name for path in (out / "new").iterdir()) == sorted(f.new_file for f in hourly_parity.FAMILIES.values())
    assert document["build"]["exit"] == 5 and document["answers"]["tables"]["raw_nws__alerts"] == "loaded"
    assert json.loads((out / hourly_parity.BUNDLE_FILE).read_text()) == document


def test_the_bundle_names_every_part_it_could_not_gather_and_never_raises(tmp_path):
    out = tmp_path / "bundle"
    warehouse = _warehouse(tmp_path / "w.duckdb", pages=False, nynjtc=False, squares=False, build_exit=None)

    document = hourly_parity.bundle(tmp_path / "no-answers", warehouse, _processed(tmp_path / "p", names=[]), out)

    assert document["answers"] is None and "the extract kept no answers" in document["inputs"]["answers"]
    assert "not in the warehouse" in document["inputs"][hourly_parity.NYNJTC_ANSWERS]
    assert "ran without the squares" in document["inputs"][hourly_parity.SQUARES]
    assert document["build"] is None and set(document["writer_files"].values()) == {None}
    assert json.loads((out / "raw" / hourly_parity.ATC_CACHE).read_text())["updates"] == {}, "no page: no automatic row"


@pytest.mark.parametrize(
    ("family", "tables", "nws_status", "says"),
    [
        ("closures", {}, 200, None),
        ("closures", {"raw_ourhike__closures": "refused"}, 200, "was refused this hour"),
        ("weather_alerts", {}, 200, None),
        ("weather_alerts", {"raw_nws__alerts": "refused"}, 200, "an earlier hour's alerts"),
        ("weather_alerts", {}, 503, "NWS answered 503"),
        ("atc_updates", {"raw_atc__atc_updates": "kept"}, 200, None),
        ("atc_updates", {"raw_atc__atc_updates": "withdrawn"}, 200, "another copy of the reviewed file"),
        ("work_projects", {"raw_ourhike__work_projects": "refused"}, 200, "another copy of the reviewed file"),
        ("nynjtc_alerts", {}, 200, None),
    ],
)
def test_a_family_whose_input_was_not_this_hours_says_why_it_was_not_compared(tmp_path, family, tables, nws_status, says):
    out = tmp_path / "bundle"
    document = hourly_parity.bundle(
        _answers(tmp_path / "answers", tables, nws_status=nws_status),
        _warehouse(tmp_path / "w.duckdb"),
        _processed(tmp_path / "p"),
        out,
    )

    reason = hourly_parity.why_not(hourly_parity.FAMILIES[family], document, out)

    assert reason is None if says is None else says in reason


def test_a_writer_the_build_held_back_is_not_compared_rather_than_a_difference(tmp_path):
    """Decision 81: the key keeps the bucket's last copy, which this hour's answers did not make."""
    out = tmp_path / "bundle"
    document = hourly_parity.bundle(
        _answers(tmp_path / "answers"),
        _warehouse(tmp_path / "w.duckdb", build_exit=5),
        _processed(tmp_path / "p", names=["conditions_reports.json"]),
        out,
    )

    assert "held part of itself back (exit 5, decision 81)" in hourly_parity.why_not(
        hourly_parity.FAMILIES["closures"], document, out
    )
    assert hourly_parity.why_not(hourly_parity.FAMILIES["reports"], document, out) is None


@pytest.mark.parametrize(
    ("outcome", "records", "new_written", "verdict"),
    [
        ("no_differences", (3, 3), True, "equal"),
        ("no_differences", (0, 0), True, "no_records"),
        ("differences", (3, 3), True, "differs"),
        ("one_side_writes", (3, None), False, "differs"),
        ("old_side_refused", (None, None), True, "differs"),
        ("old_side_refused", (None, None), False, "not_compared"),
        ("neither_writes", (None, None), False, "not_compared"),
        ("a new outcome", (None, None), True, "failed"),
    ],
)
def test_each_parity_outcome_reads_as_one_verdict(outcome, records, new_written, verdict):
    result = {"outcome": outcome, "old_records": records[0], "new_records": records[1], "message": "m", "differences": []}

    assert hourly_parity.judge(hourly_parity.FAMILIES["closures"], result, new_written)[0] == verdict


FAKE_PARITY = """
import json, sys
from pathlib import Path
args = sys.argv[1:]
family, json_dir = args[0], Path(args[args.index("--json-dir") + 1])
assert "--keys-only" in args and "--answers-dir" in args, args
if family == "reports":
    raise KeyError("a record's value, never printed")
outcome = "differences" if family == "closures" else "no_differences"
json_dir.mkdir(parents=True, exist_ok=True)
(json_dir / f"{family}.json").write_text(json.dumps({"outcome": outcome, "old_records": 2, "new_records": 2,
    "differences": [{"what": "id c1", "fields": ["note"], "held_by": ["old", "new"]}] if outcome == "differences" else [],
    "explained": []}))
print(f"{family}: 1 difference(s):" if outcome == "differences" else f"{family}: no differences")
sys.exit(1 if outcome == "differences" else 0)
"""


@pytest.fixture
def fake_parity(tmp_path, monkeypatch):
    """parity.py's stand-in, as a script the job's subprocess runs: closures differs, reports crashes, the rest agree."""
    folder = tmp_path / "pipeline"
    folder.mkdir()
    (folder / "parity.py").write_text(FAKE_PARITY)
    monkeypatch.setattr(hourly_parity, "PIPELINE_DIR", folder)
    return folder


def test_compare_runs_parity_keys_only_per_family_and_turns_red_only_for_a_difference_or_a_crash(tmp_path, fake_parity, capsys):
    bundle_dir = tmp_path / "bundle"
    hourly_parity.bundle(
        _answers(tmp_path / "answers", {"raw_nws__alerts": "refused"}),
        _warehouse(tmp_path / "w.duckdb"),
        _processed(tmp_path / "p"),
        bundle_dir,
    )
    summary = tmp_path / "summary.md"
    # As check-conditions.yml's `parity` job runs it: the build's run and commit, and the run comparing it.
    argv = ["compare", "--bundle", str(bundle_dir), "--out", str(tmp_path / "result"), "--summary", str(summary)]
    argv += ["--run", "38075292380", "--commit", "e49ca601" + "0" * 32, "--leg", "ua", "--compared-in", "38075301234"]

    code = hourly_parity.main(argv)

    run = json.loads((tmp_path / "result" / hourly_parity.RUN_FILE).read_text())
    verdicts = {name: answer["verdict"] for name, answer in run["families"].items()}
    assert code == 1
    assert verdicts == {
        "closures": "differs",
        "reports": "failed",
        "weather_alerts": "not_compared",
        "atc_updates": "equal",
        "nynjtc_alerts": "equal",
        "work_projects": "equal",
    }
    assert run["families"]["reports"]["why"] == "parity.py exited 1 without a result (KeyError)", "the type, never the value"
    assert (
        run["format"] == hourly_parity.HOURLY_FORMAT and run["run"] == "38075292380" and run["built_at"] == "2026-10-10 18:21:42"
    )
    out = capsys.readouterr().out
    assert "a record's value" not in out and "a record's value" not in summary.read_text()
    assert "::error title=conditions/closures.json against today's exporter::" in out
    assert "::warning title=conditions/weather_alerts.json not compared this hour::" in out
    page = summary.read_text()
    assert "| `conditions/closures.json` | **differs** | 2 / 2 | 1 / 0 |" in page
    # The one file not compared leads the summary, above the table, and is counted again in the closing line.
    assert page.index("**1 of the 6 files were not compared this hour.**") < page.index("| File | Answer |")
    assert "turn this run red**: `conditions/closures.json`, `conditions/reports.json`; **1 not compared**." in page
    assert "Nothing compared this hour" not in out, "the hour's own annotation is for an hour that compared nothing"
    assert "Build run 38075292380 on `e49ca6010000`" in page and "`hourly-parity-ua` artifact in run 38075301234" in page
    assert run["compared_in"] == "38075301234" and run["attempt"] is None


def test_no_bundle_reads_as_every_family_not_compared_and_the_run_stays_green(tmp_path, fake_parity, capsys):
    """Green, and impossible to miss: the summary opens on it and one annotation says it for the hour, ahead of the six
    (review finding S2-1 of PR #1805 — dlt → dbt re-platform as one go/no-go change: eight soak runs compared nothing
    and every one read clean)."""
    summary = tmp_path / "summary.md"
    code = hourly_parity.main(
        ["compare", "--bundle", str(tmp_path / "none"), "--out", str(tmp_path / "result"), "--missing", "nothing was handed on"]
        + ["--summary", str(summary)]
    )

    run = json.loads((tmp_path / "result" / hourly_parity.RUN_FILE).read_text())
    assert code == 0
    assert {answer["verdict"] for answer in run["families"].values()} == {"not_compared"}
    assert run["bundle"] == "missing: nothing was handed on"
    page = summary.read_text()
    first = page.split("\n\n")[1]
    assert first.startswith("**Nothing was compared this hour: none of the 6 files.** On its own an hour like this is")
    assert "goes red only once the leg's store has had no bundle for 2.5 hours (decision 200)" in first
    assert first.endswith("Why: no bundle: nothing was handed on")
    assert "**0 file(s) turn this run red**: none; **6 not compared**." in page
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("::warning title=Nothing compared this hour::Nothing was compared this hour: none of the 6")
    assert sum(line.startswith("::warning title=conditions/") for line in out) == 6


def test_the_summary_names_the_soak_the_gate_counts():
    """The not-compared line says how long a missed hour holds a key back, gate_report.py's SOAK_HOURS, and after how
    long without a bundle the job goes red, its SOAK_MAX_GAP_HOURS: both written out because gate_report.py imports
    this file."""
    import gate_report

    assert hourly_parity.GATE_SOAK_HOURS == gate_report.SOAK_HOURS
    assert hourly_parity.GATE_SOAK_MAX_GAP_HOURS == gate_report.SOAK_MAX_GAP_HOURS


def _stopped_at(monkeypatch, name: str, stop: type[BaseException] = KeyboardInterrupt) -> None:
    """run_family() stops when it reaches family `name`, as the runner's SIGINT does at the compare step's 3-minute
    cap; every other family answers equal at once, with no subprocess."""

    def run_family(family, bundle_dir, out, python):
        if family.name == name:
            raise stop
        return hourly_parity.FamilyAnswer(family.key, "equal", family.compared_on, outcome="no_differences")

    monkeypatch.setattr(hourly_parity, "run_family", run_family)


def test_a_comparison_stopped_part_way_leaves_run_json_naming_where_it_stopped(tmp_path, monkeypatch):
    """The 2026-10-15 review's finding S2-3: compare() wrote run.json once, after the last family, so a step killed at
    its cap or a compare() that raised left no run.json, and the gate read the hour as one that never came, which
    decision 158's gap rule absorbs. run.json is written before the first family and after each, so the family being
    compared reads `failed` (a crash, which makes the key differ) and the families after it `not_compared`."""
    bundle_dir = tmp_path / "bundle"
    hourly_parity.bundle(
        _answers(tmp_path / "answers"), _warehouse(tmp_path / "w.duckdb"), _processed(tmp_path / "p"), bundle_dir
    )
    _stopped_at(monkeypatch, "reports")

    with pytest.raises(KeyboardInterrupt):
        hourly_parity.compare(bundle_dir, tmp_path / "result", identity={"run": "38075292380", "leg": "ua"})

    run = json.loads((tmp_path / "result" / hourly_parity.RUN_FILE).read_text())
    assert run["finished"] is False and run["run"] == "38075292380" and run["built_at"] == "2026-10-10 18:21:42"
    assert {name: answer["verdict"] for name, answer in run["families"].items()} == {
        "closures": "equal",
        "reports": "failed",
        "weather_alerts": "not_compared",
        "atc_updates": "not_compared",
        "nynjtc_alerts": "not_compared",
        "work_projects": "not_compared",
    }
    assert "stopped while it compared this family" in run["families"]["reports"]["why"]
    assert "stopped before it reached this family" in run["families"]["work_projects"]["why"]
    assert [path.name for path in (tmp_path / "result").iterdir() if path.name.startswith("run")] == [hourly_parity.RUN_FILE]


KILLING_PARITY = """
import os, signal, sys
if sys.argv[1] == "reports":
    os.kill(os.getppid(), signal.SIGKILL)  # the runner's last word to a step past its cap: nothing of compare() runs after it
print(f"{sys.argv[1]}: no answer")
sys.exit(2)
"""


def test_a_comparison_killed_outright_still_leaves_run_json(tmp_path):
    """SIGKILL, the runner's last step after SIGINT and SIGTERM, runs no handler: what is on disk is what was written
    before the family began."""
    bundle_dir = tmp_path / "bundle"
    hourly_parity.bundle(
        _answers(tmp_path / "answers"), _warehouse(tmp_path / "w.duckdb"), _processed(tmp_path / "p"), bundle_dir
    )
    fake = tmp_path / "pipeline"
    fake.mkdir()
    (fake / "parity.py").write_text(KILLING_PARITY)
    driver = (
        "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import hourly_parity; "
        "hourly_parity.PIPELINE_DIR = Path(sys.argv[2]); sys.exit(hourly_parity.main(sys.argv[3:]))"
    )
    argv = ["compare", "--bundle", str(bundle_dir), "--out", str(tmp_path / "result"), "--run", "38075292380"]

    finished = subprocess.run(
        [sys.executable, "-c", driver, str(Path(hourly_parity.__file__).parent), str(fake), *argv],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert finished.returncode == -signal.SIGKILL, finished.stderr
    run = json.loads((tmp_path / "result" / hourly_parity.RUN_FILE).read_text())
    assert run["finished"] is False
    assert run["families"]["closures"]["verdict"] == "failed", "parity.py answered nothing for it, as when it crashes"
    assert (run["families"]["reports"]["verdict"], run["families"]["weather_alerts"]["verdict"]) == ("failed", "not_compared")
    assert run["families"]["reports"]["why"] == hourly_parity.STOPPED_IN


def test_the_gate_reads_an_hour_whose_comparison_stopped_as_a_crash_and_a_hole_never_as_absent(tmp_path, monkeypatch):
    """End to end, the review's case: 73 hourly builds, the comparison of hour 30 stopped while it compared reports.
    At ad932107 that hour had no run.json, so all three keys below read clear across a 2-hour gap."""
    import gate_report

    bundle_dir = tmp_path / "bundle"
    hourly_parity.bundle(
        _answers(tmp_path / "answers"), _warehouse(tmp_path / "w.duckdb"), _processed(tmp_path / "p"), bundle_dir
    )
    document = json.loads((bundle_dir / hourly_parity.BUNDLE_FILE).read_text())
    start = datetime(2026, 10, 12, 0, 18)
    for hour in range(73):
        document["build"]["started_at"] = (start + timedelta(hours=hour)).strftime("%Y-%m-%d %H:%M:%S")
        (bundle_dir / hourly_parity.BUNDLE_FILE).write_text(json.dumps(document))
        _stopped_at(monkeypatch, "reports" if hour == 30 else "no family")
        identity = {"run": str(38600000000 + hour), "attempt": "1", "commit": "e49ca601" + "0" * 32, "leg": "ua"}
        try:
            hourly_parity.compare(bundle_dir, tmp_path / "soak" / str(hour), identity=identity)
        except KeyboardInterrupt:
            assert hour == 30

    runs = gate_report.load_hourly(tmp_path / "soak")

    assert len(runs) == 73
    assert gate_report.soak_coverage(runs, "closures").state == "clear", "its comparison finished before the stop"
    reports = gate_report.soak_coverage(runs, "reports")
    assert reports.state == "differs" and "run 38600000030.1" in reports.detail and "stopped while it compared" in reports.detail
    nws = gate_report.soak_coverage(runs, "weather_alerts")
    assert nws.state == "short" and "stopped before it reached this family" in nws.detail


def test_parity_answers_dir_moves_raw_dir_for_one_comparison_and_puts_it_back(tmp_path):
    """--answers-dir: the conditions old sides read the bundle's raw/ in place of data/raw/, and the next comparison in
    the same process reads data/raw/ again."""
    before = parity.RAW_DIR
    with parity.answers_read_from(tmp_path):
        assert parity.RAW_DIR == tmp_path.resolve()
    assert parity.RAW_DIR == before
    with parity.answers_read_from(None):
        assert parity.RAW_DIR == before


def test_every_hourly_family_is_a_parity_family_writing_the_file_its_pub_writer_writes():
    writers = Path(__file__).parent.parent / "dbt" / "models" / "publish"
    for family in hourly_parity.FAMILIES.values():
        assert family.name in parity.FAMILIES
        (writer,) = [path for path in writers.glob("pub_conditions_*.sql") if f"location='{family.new_file}'" in path.read_text()]
        assert writer.stem.removeprefix("pub_conditions_") == family.key.removeprefix("conditions/").removesuffix(".json")


def test_the_runs_time_is_when_its_build_began(tmp_path, fake_parity):
    hourly_parity.bundle(
        _answers(tmp_path / "answers"), _warehouse(tmp_path / "w.duckdb"), _processed(tmp_path / "p"), tmp_path / "b"
    )
    run = hourly_parity.compare(tmp_path / "b", tmp_path / "result", python=sys.executable)
    assert datetime.fromisoformat(run["built_at"]) == datetime(2026, 10, 10, 18, 21, 42)
