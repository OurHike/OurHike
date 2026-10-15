"""gate_report.py --hourly-dir: the six conditions keys judged by their hourly comparisons on real data (soak_coverage()).

Open question 17, the maintainer's poll of 2026-10-10: "Compare every soak hour". A key the monthly lane compares
nothing for stops blocking go only when every run of the soak's last SOAK_HOURS compared it clean, none more than
SOAK_MAX_GAP_HOURS apart; one difference anywhere makes it differ. Each run here is what the parity job uploads: its
run.json (hourly_parity.py's HOURLY_FORMAT) and parity.py's keys-only result beside it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import gate_report
import hourly_parity
import parity
from gate_report import DbtKey, TodayKey, key_rows, load_hourly, soak_coverage

START = datetime(2026, 10, 10, 3, 50, tzinfo=UTC)
CLOSURES = DbtKey(
    "conditions/closures.json", "conditions_closures_json", "model.ourhike.pub_conditions_closures", "conditions_closures.json"
)
WORK = DbtKey(
    "conditions/work_projects.json",
    "conditions_work_projects_json",
    "model.ourhike.pub_conditions_work_projects",
    "conditions_work_projects.json",
)
TODAY = [TodayKey(key.key, "live", "publish.collect_artifacts(), from conditions_manifest.json") for key in (CLOSURES, WORK)]


def _result(family: str, outcome: str = "no_differences", records: int = 3, **fields) -> dict:
    new_file = hourly_parity.FAMILIES[family].new_file
    return {
        "format": parity.RESULT_FORMAT,
        "family": family,
        "new_file": f"data/hourly_parity/bundle/new/{new_file}",
        "new_file_name": new_file,
        "records": family,
        "key": "id",
        "ordered": True,
        "compared_by_form_only": ["generated_at"],
        "outcome": outcome,
        "exit_code": 0 if outcome == "no_differences" else 1,
        "message": None,
        "old_records": records,
        "new_records": records,
        "explained": [],
        "differences": [],
        **fields,
    }


#: The commit every run here is built on unless a test says otherwise: a full sha, as check-conditions.yml's
#: `--commit "$COMMIT"` (github.sha) writes it into run.json.
COMMIT = "e49ca601" + "0" * 32
OTHER = "a1b2c3d4" + "0" * 32


def _run(
    root: Path,
    hour: float,
    verdicts: dict[str, str],
    *,
    run: int | None = None,
    records: int = 3,
    leg: str = "ua",
    commit: str | None = COMMIT,
) -> Path:
    """One parity job's artifact, `hour` hours after START, as gh run download writes it: run.json and results/."""
    at = START + timedelta(hours=hour)
    number = run if run is not None else 38000000000 + int(hour * 60)
    folder = root / f"{number}-{leg}-{commit}"
    (folder / hourly_parity.RESULTS_DIR).mkdir(parents=True)
    families = {}
    for family, verdict in verdicts.items():
        outcome = {"equal": "no_differences", "no_records": "no_differences", "differs": "differences"}.get(verdict)
        answer = {"key": hourly_parity.FAMILIES[family].key, "verdict": verdict, "why": None, "result": None}
        if outcome is not None:
            differences = [{"what": "id c1", "fields": ["status"], "held_by": ["old", "new"]}] if verdict == "differs" else []
            result = _result(family, outcome, 0 if verdict == "no_records" else records, differences=differences)
            (folder / hourly_parity.RESULTS_DIR / f"{family}.json").write_text(json.dumps(result))
            answer["result"] = f"{hourly_parity.RESULTS_DIR}/{family}.json"
        else:
            answer["why"] = "raw_nws__alerts was refused this hour"
        families[family] = answer
    document = {
        "format": hourly_parity.HOURLY_FORMAT,
        "run": str(number),
        "attempt": "1",
        "commit": commit,
        "leg": leg,
        "built_at": at.strftime("%Y-%m-%d %H:%M:%S"),
        "families": families,
    }
    (folder / hourly_parity.RUN_FILE).write_text(json.dumps(document))
    return folder


def _soak(
    root: Path, hours: int = 72, step: float = 1.0, verdict: str = "equal", skip=(), changed=None, commit=COMMIT, start=0
) -> Path:
    """A run every `step` hours from START + `start` to START + `start` + `hours`, each comparing closures and
    work_projects, every one built on `commit`."""
    count = int(hours / step) + 1
    for index in range(count):
        if index in skip:
            continue
        hour = start + index * step
        verdicts = {"closures": verdict, "work_projects": "no_records"} | (changed or {}).get(index, {})
        _run(root, hour, verdicts, commit=commit)
    return root


def _row(rows, key):
    return next(row for row in rows if row.key == key)


def test_a_key_the_monthly_lane_never_compares_stops_blocking_once_every_soak_hour_compared_it_clean(tmp_path):
    runs = load_hourly(_soak(tmp_path))

    rows, _, _ = key_rows(TODAY, [CLOSURES, WORK], {}, runs)

    closures = _row(rows, "conditions/closures.json")
    assert closures.verdict == "equal_apart_from_listed" and not closures.blocks_go
    assert "every one of the 73 runs of the soak's last 72 h" in closures.detail
    assert [item.what for item in closures.listed] == ["field generated_at"], "the stamp is held to its form, and said so"


def test_without_hourly_results_the_key_still_blocks_as_a_writer_nothing_compared(tmp_path):
    rows, _, _ = key_rows(TODAY, [CLOSURES], {}, None)
    assert (_row(rows, "conditions/closures.json").why, _row(rows, "conditions/closures.json").blocks_go) == (
        "writer_without_result",
        True,
    )


def test_one_hour_that_differed_anywhere_makes_the_key_differ_and_block(tmp_path):
    runs = load_hourly(_soak(tmp_path, changed={5: {"closures": "differs"}}))

    coverage = soak_coverage(runs, "closures")
    rows, _, _ = key_rows(TODAY, [CLOSURES], {}, runs)

    closures = _row(rows, "conditions/closures.json")
    assert coverage.state == "differs" and coverage.differing == 1
    assert closures.verdict == "differs" and closures.blocks_go
    assert [(item.what, item.fields, item.safety) for item in closures.differences] == [("id c1", ["status"], ["closure fields"])]
    assert closures.differences[0].held_by == ["old", "new"], "values withheld: the hourly results are keys only"


def test_an_hour_inside_the_soak_that_compared_nothing_keeps_the_key_blocking_and_names_the_run(tmp_path):
    runs = load_hourly(_soak(tmp_path, changed={40: {"closures": "not_compared"}}))

    rows, _, _ = key_rows(TODAY, [CLOSURES], {}, runs)

    closures = _row(rows, "conditions/closures.json")
    assert (closures.verdict, closures.why, closures.blocks_go) == ("not_ported", "soak_not_covered", True)
    assert "1 of the 73 runs in the soak's last 72 h did not compare it clean" in closures.detail
    assert "raw_nws__alerts was refused this hour" in closures.detail


def test_two_missing_hours_in_a_row_are_a_gap_the_soak_has_to_cover_again(tmp_path):
    """Runs that never came leave no result at all, so only the time between the runs that did can show them."""
    runs = load_hourly(_soak(tmp_path, skip=(30, 31)))

    coverage = soak_coverage(runs, "closures")

    assert coverage.state == "short"
    assert (
        "3.0 h apart" in coverage.detail
        and f"more than SOAK_MAX_GAP_HOURS ({gate_report.SOAK_MAX_GAP_HOURS} h)" in coverage.detail
    )


def test_dispatch_jitter_and_one_missing_hour_still_cover_the_soak(tmp_path):
    """SOAK_MAX_GAP_HOURS takes the jitter the soak's routine shows (55.6 to 63.0 minutes between runs 617 and 624) and
    one missed hour (decision 158: run 629 at 22:18 and run 631 at 00:15 UTC, a container restart between them). Two in a
    row are refused, in the test above."""
    root = tmp_path / "jitter"
    for index in range(73):
        _run(root, index + (0.05 if index % 2 else -0.05) if 0 < index < 72 else index, {"closures": "equal"})
    assert soak_coverage(load_hourly(root), "closures").state == "clear"
    assert soak_coverage(load_hourly(_soak(tmp_path / "missing", skip=(30,))), "closures").state == "clear"


def test_a_soak_shorter_than_SOAK_HOURS_keeps_the_key_blocking(tmp_path):
    coverage = soak_coverage(load_hourly(_soak(tmp_path, hours=48)), "closures")

    assert coverage.state == "short" and "span 48.0 h" in coverage.detail and "short of the soak's 72 h" in coverage.detail


def test_only_the_ua_legs_runs_cover_the_soak_and_any_legs_difference_still_counts(tmp_path):
    """Decision 46 soaks the UA leg (SOAK_LEG): a production run in the hour UA missed does not fill it, and a
    production run that differed makes the key differ all the same."""
    root = _soak(tmp_path / "hole", skip=(30, 31))
    for hour in (30, 31):
        _run(root, hour, {"closures": "equal"}, leg="production")
    assert soak_coverage(load_hourly(root), "closures").state == "short"

    root = _soak(tmp_path / "differs")
    _run(root, 30.5, {"closures": "differs"}, leg="production")
    assert soak_coverage(load_hourly(root), "closures").state == "differs"

    only_production = tmp_path / "production"
    _run(only_production, 0, {"closures": "equal"}, leg="production")
    coverage = soak_coverage(load_hourly(only_production), "closures")
    assert coverage.state == "short" and "no hourly comparison of the ua leg (SOAK_LEG) was read" in coverage.detail


def test_a_soak_run_on_an_older_commit_never_covers_the_newest_one(tmp_path):
    """The 2026-10-15 review's finding S2-2: 73 clean hours built on one commit and a single hour on the next read
    `clear`, as if the 72 hours had run the newest code. Decision 112 asks for a fresh soak on the final branch, and
    decisions 142 and 148 restart it on a push that changes the hourly lane. Each run.json names the commit its build
    ran (check-conditions.yml passes github.sha, and take-bundle refuses a bundle another commit's build put), so the
    soak judged is the newest ua run's commit, and every other commit's run is set aside and said."""
    root = _soak(tmp_path, commit=OTHER)
    _run(root, 73, {"closures": "equal"})

    coverage = soak_coverage(load_hourly(root), "closures")

    assert coverage.state == "short", coverage.detail
    assert "span 0.0 h" in coverage.detail and "built on e49ca6010000" in coverage.detail
    assert "set aside 73 runs of the ua leg built on another commit: 73 on a1b2c3d40000 (2026-10-10 03:50 UTC to " in (
        coverage.detail
    )


def test_another_branchs_ua_runs_never_fill_an_hour_of_the_soak(tmp_path):
    """gh run download of every check-conditions run fetches other branches' hourly-parity-ua too: two of them in the
    judged commit's two missing hours (decision 158 allows one) leave the gap a gap."""
    root = _soak(tmp_path, skip=(30, 31))
    for hour in (30, 31):
        _run(root, hour, {"closures": "equal"}, commit=OTHER)

    coverage = soak_coverage(load_hourly(root), "closures")

    assert coverage.state == "short" and "3.0 h apart" in coverage.detail, coverage.detail
    assert "set aside 2 runs of the ua leg built on another commit: 2 on a1b2c3d40000" in coverage.detail


def test_the_commit_judged_can_be_named_and_a_commit_whose_hourly_lane_is_the_same_added(tmp_path):
    """--commit names the commit judged, in full or by its first seven characters or more. Decision 142 restarts the
    soak only for a push that changes the hourly lane, so a second --commit counts a commit the person running the gate
    vouches for, and the answer names both."""
    root = _soak(tmp_path, hours=40, commit=OTHER)
    _soak(root, hours=31, start=41)
    runs = load_hourly(root)

    newest_only = soak_coverage(runs, "closures")
    older_named = soak_coverage(runs, "closures", commits=[OTHER[:7]])
    both = soak_coverage(runs, "closures", commits=[COMMIT, OTHER[:12]])

    assert newest_only.state == "short" and "span 31.0 h" in newest_only.detail
    assert older_named.state == "short" and "span 40.0 h" in older_named.detail
    assert "set aside 32 runs of the ua leg built on another commit: 32 on e49ca6010000" in older_named.detail
    assert both.state == "clear" and "commits judged e49ca6010000, a1b2c3d40000" in both.detail, both.detail
    assert "set aside" not in both.detail


def test_a_short_commit_a_run_json_names_still_matches_itself_and_nothing_shorter_than_git_s_seven(tmp_path):
    """CI writes github.sha in full; a run.json written by hand may name `c0ffee`, as the review's own script did. The
    newest run's commit is judged by default, so its runs count, and a prefix under 7 characters matches no other."""
    root = _soak(tmp_path, commit="c0ffee")

    assert soak_coverage(load_hourly(root), "closures").state == "clear"
    assert soak_coverage(load_hourly(_soak(tmp_path / "full")), "closures", commits=[COMMIT[:6]]).state == "short"


def test_a_run_naming_no_commit_is_set_aside_and_said(tmp_path):
    root = _soak(tmp_path)
    _run(root, 30.5, {"closures": "equal"}, commit=None)

    coverage = soak_coverage(load_hourly(root), "closures")

    assert coverage.state == "clear" and "set aside 1 run of the ua leg naming no commit" in coverage.detail
    nameless = tmp_path / "nameless"
    _run(nameless, 0, {"closures": "equal"}, commit=None)
    assert "names no commit, so which code the soak ran is unknown" in soak_coverage(load_hourly(nameless), "closures").detail


def test_a_difference_on_any_commit_still_makes_the_key_differ_and_names_that_commit(tmp_path):
    """Strict on purpose: a difference found on an older commit may be a defect the newer one still has, on data its
    hours never met, so it stays until somebody reads it and takes that run out of --hourly-dir."""
    root = _soak(tmp_path)
    _run(root, 10.5, {"closures": "differs"}, commit=OTHER)

    coverage = soak_coverage(load_hourly(root), "closures")

    assert coverage.state == "differs"
    assert "on a1b2c3d40000, not a commit judged" in coverage.detail


def test_main_judges_the_commit_named_says_which_and_refuses_one_that_is_not_a_commit(tmp_path):
    arguments = _report_arguments(tmp_path)
    root = _soak(tmp_path / "soak", commit=OTHER)
    _run(root, 73, {"closures": "equal"})

    assert gate_report.main([*arguments, "--hourly-dir", str(root), "--commit", "e49c"]) == 2
    assert gate_report.main([*arguments, "--commit", OTHER]) == 2, "--commit judges the hourly runs, so it needs them"
    assert gate_report.main([*arguments, "--hourly-dir", str(root), "--strict"]) == 1
    newest = json.loads((tmp_path / "out" / "gate_report.json").read_text())
    assert newest["inputs"]["hourly_commits"] == [COMMIT]
    assert "built on a commit judged (e49ca6010000; the newest ua run's)" in (tmp_path / "out" / "gate_report.md").read_text()
    assert gate_report.main([*arguments, "--hourly-dir", str(root), "--commit", OTHER, "--strict"]) == 0

    report = json.loads((tmp_path / "out" / "gate_report.json").read_text())
    assert report["inputs"]["hourly_commits"] == [OTHER]
    markdown = (tmp_path / "out" / "gate_report.md").read_text()
    assert "built on a commit judged (a1b2c3d40000; named by --commit)" in markdown
    assert "set aside 1 run of the ua leg built on another commit: 1 on e49ca6010000" in markdown


def test_comparisons_of_two_empty_files_count_only_for_a_family_the_monthly_rule_lets_be_empty(tmp_path, monkeypatch):
    """The real reviewed work-projects file holds no rows, so each hour compares two empty lists: the monthly lane's
    MAY_COMPARE_NO_RECORDS rule decides whether that says anything, here as there."""
    runs = load_hourly(_soak(tmp_path))
    monkeypatch.delitem(gate_report.MAY_COMPARE_NO_RECORDS, "work_projects")
    rows, _, _ = key_rows(TODAY, [WORK], {}, runs)
    assert _row(rows, "conditions/work_projects.json").why == "soak_not_covered"
    assert "equal, no records" not in _row(rows, "conditions/work_projects.json").detail

    # Decision 162 lists it, with its reason.
    monkeypatch.setitem(gate_report.MAY_COMPARE_NO_RECORDS, "work_projects", "the reviewed file holds no rows")
    rows, _, _ = key_rows(TODAY, [WORK], {}, runs)
    assert not _row(rows, "conditions/work_projects.json").blocks_go


def test_a_monthly_result_judges_its_key_unless_an_hourly_comparison_differs(tmp_path):
    monthly = {"closures": _result("closures")}
    clean = load_hourly(_soak(tmp_path / "clean", hours=10))
    rows, unmatched, _ = key_rows(TODAY, [CLOSURES], monthly, clean)
    assert _row(rows, "conditions/closures.json").verdict == "equal_apart_from_listed" and unmatched == []

    differing = load_hourly(_soak(tmp_path / "differing", hours=10, changed={3: {"closures": "differs"}}))
    rows, unmatched, _ = key_rows(TODAY, [CLOSURES], monthly, differing)
    assert _row(rows, "conditions/closures.json").verdict == "differs" and unmatched == []


def test_a_run_json_in_another_format_is_refused_by_name(tmp_path):
    (tmp_path / "1").mkdir()
    (tmp_path / "1" / hourly_parity.RUN_FILE).write_text(json.dumps({"format": "something else"}))

    with pytest.raises(ValueError, match="is not an hourly comparison"):
        load_hourly(tmp_path)


def _report_arguments(tmp_path: Path) -> list[str]:
    """gate_report.py's arguments over a dbt manifest whose one exposure is the closures writer, and one monthly
    parity result that reaches no key of it."""
    manifest = {
        "nodes": {CLOSURES.writer: {"config": {"materialized": "phone_file", "location": CLOSURES.location}}},
        "exposures": {
            "exposure.ourhike.conditions_closures_json": {
                "name": CLOSURES.exposure,
                "config": {"meta": {"r2_keys": [CLOSURES.key]}},
                "depends_on": {"nodes": [CLOSURES.writer]},
            }
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "parity").mkdir()
    (tmp_path / "parity" / "spurs.json").write_text(
        json.dumps({**_result("closures"), "family": "spurs", "new_file_name": "spurs.json"})
    )
    return [
        "--parity-dir",
        str(tmp_path / "parity"),
        "--out",
        str(tmp_path / "out"),
        "--dbt-manifest",
        str(tmp_path / "manifest.json"),
    ]


def test_main_reads_the_soaks_artifacts_and_says_so_and_refuses_a_folder_with_none(tmp_path):
    arguments = _report_arguments(tmp_path)
    (tmp_path / "empty").mkdir()

    assert gate_report.main([*arguments, "--hourly-dir", str(tmp_path / "empty")]) == 2
    assert gate_report.main([*arguments, "--hourly-dir", str(_soak(tmp_path / "soak")), "--strict"]) == 0

    report = json.loads((tmp_path / "out" / "gate_report.json").read_text())
    closures = next(row for row in report["keys"] if row["key"] == "conditions/closures.json")
    assert closures["verdict"] == "equal_apart_from_listed" and closures["family"] == "closures"
    assert report["inputs"]["hourly_runs"] == 73
    markdown = (tmp_path / "out" / "gate_report.md").read_text()
    assert "73 hourly comparisons on real data" in markdown and "every run of the soak's last 72 h" in markdown
