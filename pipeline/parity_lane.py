"""The monthly lane's parity: one group of families in one process, so the exporter runs they share run once.

    python parity_lane.py --group network --out "$RUNNER_TEMP/parity"
    python parity_lane.py --join "$RUNNER_TEMP/parity" --raw-run "$RAW_RUN"

build-reference.yml's `parity` job runs each group in GROUPS on a runner of
its own, side by side, and `parity-report` joins their answers into the one
`monthly-parity` artifact gate_report.py reads (decision 30's parity on frozen
inputs: pipeline-tests.yml's parity families less the six hourly conditions
files, FAMILIES below).

WHY GROUPS, AND WHY ONE PROCESS EACH. Monthly run 29 (refresh-reference.yml
37726904273, 2026-10-08) ran every family as a parity.py process of its own,
one after another, and its 120 minutes ran out on the twelfth of 41:
nearby_trails took 36.8 minutes, network_overview 14.3 and spurs 16.3, and
trail_graph_elevation had run 42 minutes when the job was cancelled. Each
process re-ran the exporters the families share. parity.py caches those runs
for its process (functools.cache on _published_network(), _export_trails_run(),
_cut_trails(), _published_pois(), _osm_water_old(), _graph_companions_old() and
_trail_graph_built()), so a group whose families share one runs it once. The
vector build's own step times say which are worth sharing (publish-vector-data
run 37114537637, 2026-10-03): export_nearby_trails.py 13 m 13 s,
build_trail_graph.py 40 m 57 s and export_network_elevation.py 39 m 43 s,
against 19 s for export_poi.py; and the eight POI families each grade OSM
water against EPQS through _osm_water_old(). The groups run side by side
because the slowest ones share nothing: the network, the graph, and the DEM
sampling behind the graph's climbs.

EACH FAMILY STILL SEES THE MODULES AS A PROCESS OF ITS OWN WOULD. The old sides
set module paths on the exporters they run (export_poi's NETWORK_LINES_PATH,
TRAIL_WATER_PATH and photo files, export_nearby_trails' and export_trails'
OUT_DIR), and some never put them back, which a family in a process of its own
never sees. So after each family, every module from this folder that the
family imported is dropped (isolated()), and the next family imports it afresh,
with its defaults. parity.py's cached runs are files and plain data, so they
outlive the modules that made them.

EVERY ANSWER IS KEYS ONLY (parity.py's --keys-only): the artifact is public, and
the old side runs on every layer the pin holds, held-back sources included. So
each difference is named by key and changed fields, never with either record.
To see the records, rerun that family's parity.py line without the flag, on the
raw_run's pin, as build-reference.yml's parity job sets it up.

A difference is evidence for the gate, not a failure of the lane: a group fails
only when none of its families could be compared. Each family's console is kept
as <family>.txt, its result as results/<family>.json (gate_report.py refuses
any other JSON there), and the group's answers as summary-<group>.json, which
--join folds into summary.json.
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import json
import os
import sys
import traceback
from collections.abc import Callable, Iterator
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent

#: Each family's file from its pub_ writer, under data/processed/dbt/, and
#: whether its old side is handed data/raw (parity.py's --raw-dir): the raw
#: files, or for the graph's climbs the DEM tiles under it. A literal, so
#: .github/tests/test_build_reference.py reads it without importing this file
#: and holds it to pipeline-tests.yml's families.
FAMILIES = {
    "podcasts": ("podcasts_episodes.json", False),
    "stewards": ("stewards.json", False),
    "registry": ("registry.json", False),
    "nearby_trails": ("nearby_trails.geojson", False),
    "network_overview": ("network_overview.geojson", False),
    "trails": ("trails.geojson", False),
    "trail_miles": ("trail_miles.json", False),
    "trails_overview": ("trails_overview.geojson", False),
    "spurs": ("spurs.json", False),
    "club_sections": ("club_sections.json", False),
    "elevation": ("elevation_profile.json", True),
    "trail_graph_elevation": ("trail_graph_elevation.json", True),
    "trail_graph_profile": ("trail_graph_profile.json", True),
    "poi_shelter": ("poi_shelter.geojson", False),
    "poi_campsite": ("poi_campsite.geojson", False),
    "poi_water": ("poi_water.geojson", False),
    "poi_resupply": ("poi_resupply.geojson", False),
    "poi_viewpoint": ("poi_viewpoint.geojson", False),
    "poi_parking": ("poi_parking.geojson", False),
    "poi_privy": ("poi_privy.geojson", False),
    "poi_trailhead": ("poi_trailhead.geojson", False),
    "nearby_poi": ("nearby_poi.geojson", False),
    "retired_poi": ("retired_poi.geojson", False),
    "suggested_hikes": ("suggested_hikes.json", True),
    "suggested_hikes_detail": ("suggested_hikes_detail.json", True),
    "highlights": ("highlights.json", True),
    "places": ("places.json", False),
    "challenges": ("challenges.json", False),
    "trail_graph": ("trail_graph.json", False),
    "trail_graph_geometry": ("trail_graph_geometry.json", False),
    # Stage 6's v2 files, each against the v1 file this build wrote beside it.
    "elevation_v2": ("elevation_profile_v2.json", False),
    "trail_miles_v2": ("trail_miles_v2.json", False),
    "poi_shelter_v2": ("poi_shelter_v2.geojson", False),
    "poi_campsite_v2": ("poi_campsite_v2.geojson", False),
    "poi_water_v2": ("poi_water_v2.geojson", False),
    "poi_resupply_v2": ("poi_resupply_v2.geojson", False),
    "poi_viewpoint_v2": ("poi_viewpoint_v2.geojson", False),
    "poi_parking_v2": ("poi_parking_v2.geojson", False),
    "poi_privy_v2": ("poi_privy_v2.geojson", False),
    "poi_trailhead_v2": ("poi_trailhead_v2.geojson", False),
    "nearby_poi_v2": ("nearby_poi_v2.geojson", False),
}

#: Which families share a process, by the run they share (the module
#: docstring). Every family is in exactly one group.
GROUPS = {
    # export_nearby_trails.main(), once for both of its files (_published_network()).
    "network": ("nearby_trails", "network_overview"),
    # The published network again, under every POI file, the places, the
    # challenges and the spurs' destinations.
    "pois": (
        "poi_shelter",
        "poi_campsite",
        "poi_water",
        "poi_resupply",
        "poi_viewpoint",
        "poi_parking",
        "poi_privy",
        "poi_trailhead",
        "nearby_poi",
        "places",
        "challenges",
        "spurs",
    ),
    # build_trail_graph.build(), once for the graph and its geometry (_trail_graph_built()).
    "graph": ("trail_graph", "trail_graph_geometry"),
    # The DEM sampling along every edge, once for the climbs and the profiles (_graph_companions_old()).
    "graph_climbs": ("trail_graph_elevation", "trail_graph_profile"),
    # Everything that shares nothing slow: the A.T.'s own files, the registry,
    # the hikes and the v2 files, which read only what the build wrote.
    "rest": (
        "podcasts",
        "stewards",
        "registry",
        "trails",
        "trail_miles",
        "trails_overview",
        "club_sections",
        "elevation",
        "retired_poi",
        "suggested_hikes",
        "suggested_hikes_detail",
        "highlights",
        "elevation_v2",
        "trail_miles_v2",
        "poi_shelter_v2",
        "poi_campsite_v2",
        "poi_water_v2",
        "poi_resupply_v2",
        "poi_viewpoint_v2",
        "poi_parking_v2",
        "poi_privy_v2",
        "poi_trailhead_v2",
        "nearby_poi_v2",
    ),
}

#: parity.py's result_document() outcomes, as the summary reads them. A family
#: with no results/<family>.json crashed before parity.py's finish() wrote one,
#: so it is not_compared too.
STATUSES = {
    "no_differences": "match",
    "neither_writes": "match",
    "differences": "differs",
    "one_side_writes": "differs",
    "old_side_refused": "not_compared",
}

KEEP = frozenset({"parity", "parity_lane"})


def family_argv(family: str, results: Path) -> list[str]:
    """parity.py's command line for one family, keys only, its result under `results`."""
    name, reads_raw = FAMILIES[family]
    raw = ["--raw-dir", "data/raw"] if reads_raw else []
    return [family, "--new", f"data/processed/dbt/{name}", *raw, "--json-dir", str(results), "--keys-only"]


def _from_this_folder(module) -> bool:
    path = getattr(module, "__file__", None)
    return path is not None and Path(path).resolve().parent == PIPELINE


@contextlib.contextmanager
def isolated() -> Iterator[None]:
    """Drop, on the way out, every module from this folder that was imported inside, but parity and this file."""
    before = set(sys.modules)
    try:
        yield
    finally:
        for name in set(sys.modules) - before - KEEP:
            if _from_this_folder(sys.modules[name]):
                del sys.modules[name]


def run_family(family: str, out: Path, main: Callable[[list[str]], int]) -> int:
    """One family through `main` (parity.main), its console into <out>/<family>.txt; its exit code, 2 on a crash."""
    with (out / f"{family}.txt").open("w", encoding="utf-8") as console:
        with contextlib.redirect_stdout(console), contextlib.redirect_stderr(console), isolated():
            try:
                return int(main(family_argv(family, out / "results")) or 0)
            except SystemExit as stop:
                return stop.code if isinstance(stop.code, int) else 1
            except Exception:  # noqa: BLE001 - one family's crash is that family's answer, not the group's end
                traceback.print_exc()
                return 2


def status_of(family: str, out: Path) -> str:
    result = out / "results" / f"{family}.json"
    return STATUSES[json.loads(result.read_text(encoding="utf-8"))["outcome"]] if result.exists() else "not_compared"


def run_group(group: str, out: Path, main: Callable[[list[str]], int] | None = None) -> dict:
    """Every family of `group`, in GROUPS' order, one after another in this process; {family: entry}, also written
    as <out>/summary-<group>.json.

    The summary is rewritten after every family, so a group stopped at the job's
    timeout still hands the join an answer for each family it finished, and the
    rest read as not compared.
    """
    if main is None:
        import parity

        main = parity.main
    (out / "results").mkdir(parents=True, exist_ok=True)
    summary = {}
    for family in GROUPS[group]:
        code = run_family(family, out, main)
        name, _ = FAMILIES[family]
        summary[family] = {
            "status": status_of(family, out),
            "exit_code": code,
            "new": f"data/processed/dbt/{name}",
            "log": f"{family}.txt",
        }
        _write_summary(out, group, summary)
        print(f"{family}: {summary[family]['status']}", flush=True)
        # The family's two documents are garbage now; a process of its own
        # would have handed their memory back by exiting.
        gc.collect()
    return summary


def _write_summary(out: Path, group: str, summary: dict) -> None:
    """<out>/summary-<group>.json, replaced whole, so a reader never meets half a file."""
    path = out / f"summary-{group}.json"
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps({"group": group, "families": summary}, indent=2), encoding="utf-8")
    partial.replace(path)


def join(out: Path, raw_run: str) -> dict:
    """Every summary-<group>.json under `out` folded into summary.json, with each family no group answered for as
    not_compared, so a group that never ran reads as one."""
    summary = {}
    for path in sorted(out.glob("summary-*.json")):
        summary.update(json.loads(path.read_text(encoding="utf-8"))["families"])
    for family in FAMILIES:
        summary.setdefault(family, {"status": "not_compared", "exit_code": None, "new": None, "log": None})
    document = {"raw_run": raw_run, "families": {family: summary[family] for family in FAMILIES}}
    (out / "summary.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    return document


def counts(summary: dict) -> dict:
    return {
        status: sum(entry["status"] == status for entry in summary.values()) for status in ("match", "differs", "not_compared")
    }


def step_summary(document: dict) -> str:
    """summary.json as the Markdown table the parity-report job's page shows, a row per family in FAMILIES' order."""
    rows = "".join(f"| {family} | {entry['status']} |\n" for family, entry in document["families"].items())
    return f"## Parity on raw_run `{document['raw_run']}`\n\n| family | answer |\n|---|---|\n{rows}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--group", choices=sorted(GROUPS), help="run this group's families")
    action.add_argument("--join", type=Path, help="fold the summary-<group>.json files in this folder into summary.json")
    parser.add_argument("--out", type=Path, help="the folder each family's console and result go to (--group)")
    parser.add_argument("--raw-run", default="", help="the pin's raw_run, recorded in summary.json (--join)")
    args = parser.parse_args(argv)

    if args.join is not None:
        document = join(args.join, args.raw_run)
        print(f"parity on raw_run {args.raw_run}: {counts(document['families'])}")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as page:
                page.write(step_summary(document))
        return 0
    if args.out is None:
        parser.error("--group needs --out")
    summary = run_group(args.group, args.out)
    found = counts(summary)
    print(f"parity group {args.group}: {found}")
    return 1 if found["match"] + found["differs"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
