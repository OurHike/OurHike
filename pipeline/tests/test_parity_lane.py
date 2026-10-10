"""parity_lane.py, the monthly lane's parity: every family in one group, keys only, and a crash is that family's answer.

build-reference.yml's parity job runs one group of families per runner, each
group in one process (parity_lane.py's docstring has monthly run 29's timings,
which are why). These hold what that has to keep from the one-process-per-family
form it replaced: every family still runs, every answer is keys only, one
family's crash or exit does not end its group, the modules an old side changes
do not reach the next family, and a group that never ran reads as not compared.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import parity
import parity_lane

# --- the families and the groups ---------------------------------------------


def test_every_family_is_in_exactly_one_group():
    grouped = [family for families in parity_lane.GROUPS.values() for family in families]

    assert sorted(grouped) == sorted(parity_lane.FAMILIES), "a family in no group, or in two, or a group naming no family"


def test_every_family_is_one_parity_py_knows():
    assert set(parity_lane.FAMILIES) <= set(parity.FAMILIES)


def test_a_family_is_handed_the_raw_files_exactly_when_its_old_side_reads_them():
    # A family that reads the warehouse is handed --raw-dir too: the graph's climbs sample the DEM tiles under it.
    for family, (_name, reads_raw) in parity_lane.FAMILIES.items():
        entry = parity.FAMILIES[family]
        assert reads_raw == (entry.reads_raw_dir or entry.reads_warehouse), family


@pytest.mark.parametrize("family", sorted(parity_lane.FAMILIES))
def test_every_family_runs_keys_only_with_its_result_under_results(family, tmp_path):
    argv = parity_lane.family_argv(family, tmp_path / "results")
    name, reads_raw = parity_lane.FAMILIES[family]

    assert argv[0] == family
    assert "--keys-only" in argv, "the monthly-parity artifact is public"
    assert argv[argv.index("--json-dir") + 1] == str(tmp_path / "results")
    assert argv[argv.index("--new") + 1] == f"data/processed/dbt/{name}"
    assert ("--raw-dir" in argv) == reads_raw


# --- running a group ---------------------------------------------------------


def _stub_main(outcomes: dict, calls: list):
    """parity.main's stand-in: each family's entry in `outcomes` is a parity.py outcome to write, an exception to
    raise, or SystemExit's code."""

    def main(argv: list[str]) -> int:
        calls.append(argv)
        family = argv[0]
        outcome = outcomes.get(family, "no_differences")
        print(f"{family}: compared")
        if isinstance(outcome, BaseException):
            raise outcome
        results = Path(argv[argv.index("--json-dir") + 1])
        results.mkdir(parents=True, exist_ok=True)
        (results / f"{family}.json").write_text(json.dumps({"outcome": outcome}), encoding="utf-8")
        return 0

    return main


def test_a_group_runs_each_of_its_families_in_order_and_writes_its_summary(tmp_path):
    calls: list = []
    summary = parity_lane.run_group("graph", tmp_path, _stub_main({"trail_graph_geometry": "differences"}, calls))

    assert [argv[0] for argv in calls] == list(parity_lane.GROUPS["graph"])
    assert {family: entry["status"] for family, entry in summary.items()} == {
        "trail_graph": "match",
        "trail_graph_geometry": "differs",
    }
    written = json.loads((tmp_path / "summary-graph.json").read_text(encoding="utf-8"))
    assert written == {"group": "graph", "families": summary}
    assert (tmp_path / "trail_graph.txt").read_text(encoding="utf-8") == "trail_graph: compared\n"


def test_a_family_that_crashes_is_not_compared_and_the_next_family_still_runs(tmp_path):
    calls: list = []
    outcomes = {"nearby_trails": RuntimeError("an input no pin holds")}
    summary = parity_lane.run_group("network", tmp_path, _stub_main(outcomes, calls))

    assert [argv[0] for argv in calls] == ["nearby_trails", "network_overview"]
    assert summary["nearby_trails"]["status"] == "not_compared" and summary["nearby_trails"]["exit_code"] == 2
    assert "RuntimeError: an input no pin holds" in (tmp_path / "nearby_trails.txt").read_text(encoding="utf-8")
    assert summary["network_overview"]["status"] == "match"


def test_a_family_that_exits_keeps_its_code_and_does_not_end_the_group(tmp_path):
    calls: list = []
    outcomes = {"trail_graph_elevation": SystemExit(3), "trail_graph_profile": SystemExit("refused")}
    summary = parity_lane.run_group("graph_climbs", tmp_path, _stub_main(outcomes, calls))

    assert [argv[0] for argv in calls] == ["trail_graph_elevation", "trail_graph_profile"]
    assert summary["trail_graph_elevation"]["exit_code"] == 3
    assert summary["trail_graph_profile"]["exit_code"] == 1
    assert {entry["status"] for entry in summary.values()} == {"not_compared"}


def test_the_summary_holds_every_finished_family_before_the_next_one_starts(tmp_path):
    """A group stopped at the job's timeout uploads what it has: the families it finished keep their answers."""
    seen: list = []
    main = _stub_main({}, [])

    def watching(argv: list[str]) -> int:
        summary = tmp_path / "summary-network.json"
        seen.append(sorted(json.loads(summary.read_text(encoding="utf-8"))["families"]) if summary.exists() else None)
        return main(argv)

    parity_lane.run_group("network", tmp_path, watching)

    assert seen == [None, ["nearby_trails"]]
    assert not list(tmp_path.glob("*.partial"))


def test_an_old_side_that_refused_is_not_compared(tmp_path):
    summary = parity_lane.run_group("graph", tmp_path, _stub_main({"trail_graph": "old_side_refused"}, []))

    assert summary["trail_graph"]["status"] == "not_compared"


def test_a_group_fails_only_when_none_of_its_families_could_be_compared(tmp_path, monkeypatch):
    answers = {"trail_graph": {"status": "not_compared"}, "trail_graph_geometry": {"status": "not_compared"}}
    monkeypatch.setattr(parity_lane, "run_group", lambda group, out: answers)
    assert parity_lane.main(["--group", "graph", "--out", str(tmp_path)]) == 1

    answers["trail_graph_geometry"] = {"status": "differs"}
    assert parity_lane.main(["--group", "graph", "--out", str(tmp_path)]) == 0


# --- each family sees the modules a process of its own would ------------------


def test_a_module_an_old_side_changes_comes_back_with_its_defaults_for_the_next_family(tmp_path, monkeypatch):
    (tmp_path / "lane_probe_exporter.py").write_text('OUT_DIR = "data/processed"\n', encoding="utf-8")
    monkeypatch.setattr(parity_lane, "PIPELINE", tmp_path.resolve())
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "lane_probe_exporter", raising=False)

    with parity_lane.isolated():
        import lane_probe_exporter

        lane_probe_exporter.OUT_DIR = "/tmp/elsewhere"
    assert "lane_probe_exporter" not in sys.modules

    import lane_probe_exporter

    assert lane_probe_exporter.OUT_DIR == "data/processed"
    del sys.modules["lane_probe_exporter"]


def test_a_module_imported_before_the_family_and_parity_itself_are_kept(tmp_path, monkeypatch):
    (tmp_path / "lane_probe_before.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(parity_lane, "PIPELINE", tmp_path.resolve())
    monkeypatch.syspath_prepend(str(tmp_path))
    import lane_probe_before

    try:
        with parity_lane.isolated():
            pass
        assert sys.modules["lane_probe_before"] is lane_probe_before
    finally:
        del sys.modules["lane_probe_before"]


def test_parity_and_its_cached_runs_outlive_every_family(monkeypatch):
    # parity.py is imported inside the family here, so only KEEP holds it.
    monkeypatch.delitem(sys.modules, "parity")
    with parity_lane.isolated():
        import parity as inside
    assert sys.modules["parity"] is inside


def test_a_module_from_outside_this_folder_is_never_dropped(tmp_path, monkeypatch):
    elsewhere = tmp_path / "site"
    elsewhere.mkdir()
    (elsewhere / "lane_probe_library.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(elsewhere))

    try:
        with parity_lane.isolated():
            import lane_probe_library  # noqa: F401 - imported to be kept
        assert "lane_probe_library" in sys.modules
    finally:
        sys.modules.pop("lane_probe_library", None)


# --- the shared network run -----------------------------------------------------


def test_the_network_families_read_the_one_run_published_network_keeps(tmp_path, monkeypatch):
    import export_nearby_trails

    network = tmp_path / "nearby_trails.geojson"
    network.write_text('{"type": "FeatureCollection", "features": [], "file": "nearby"}', encoding="utf-8")
    (tmp_path / "network_overview.geojson").write_text('{"type": "FeatureCollection", "file": "overview"}', encoding="utf-8")
    monkeypatch.setattr(parity, "_published_network", lambda: network)
    monkeypatch.setattr(export_nearby_trails, "main", lambda: pytest.fail("the network ran a second time"))

    assert parity._network_old("nearby_trails.geojson")["file"] == "nearby"
    assert parity._network_old("network_overview.geojson")["file"] == "overview"


# --- joining the groups ---------------------------------------------------------


def test_the_join_folds_every_group_in_familys_order_and_a_group_that_never_ran_is_not_compared(tmp_path):
    parity_lane.run_group("graph", tmp_path, _stub_main({}, []))
    parity_lane.run_group("network", tmp_path, _stub_main({"nearby_trails": "differences"}, []))

    document = parity_lane.join(tmp_path, "20261008T041900Z")

    assert document["raw_run"] == "20261008T041900Z"
    assert list(document["families"]) == list(parity_lane.FAMILIES)
    statuses = {family: entry["status"] for family, entry in document["families"].items()}
    assert statuses["nearby_trails"] == "differs" and statuses["trail_graph"] == "match"
    never_ran = set(parity_lane.GROUPS["pois"]) | set(parity_lane.GROUPS["graph_climbs"]) | set(parity_lane.GROUPS["rest"])
    assert {statuses[family] for family in never_ran} == {"not_compared"}
    assert document["families"]["spurs"]["log"] is None
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == document


def test_the_join_writes_one_table_row_per_family_to_the_step_summary(tmp_path, monkeypatch):
    parity_lane.run_group("graph", tmp_path, _stub_main({}, []))
    page = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(page))

    assert parity_lane.main(["--join", str(tmp_path), "--raw-run", "29"]) == 0

    text = page.read_text(encoding="utf-8")
    assert text.startswith("## Parity on raw_run `29`\n")
    assert "| trail_graph | match |\n" in text and "| spurs | not_compared |\n" in text
    assert text.count("\n| ") == len(parity_lane.FAMILIES) + 1  # the header and one row per family
