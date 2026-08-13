"""Answer "did the pipeline actually produce complete, correct output?"
after export and before publish - check_freshness.py's output-side sibling.

check_freshness.py asks whether anything UPSTREAM has changed, before any
fetching happens. This module asks the opposite-facing question, after
everything has already run: does what actually landed in data/processed/
(and data/raw/topo_quads/) match what the pipeline was supposed to
produce? The two never overlap - freshness is about whether source data
changed; completeness is about whether THIS run's own output can be
trusted, regardless of whether the source changed at all. A run can
process perfectly fresh input and still ship broken output (a bug in a
normalizer, an interrupted write, a script whose own gate got bypassed) -
that failure mode is what this module exists to catch, one step before
publish.py would otherwise ship it to R2.

Runs after export_trails.py, export_poi.py, export_elevation.py, and the
raster assemble (assemble_raster.py), and before publish.py, per the
documented pipeline run order (see README.md).

    .venv/Scripts/python check_output_quality.py

FIVE CHECKS, IN PRIORITY ORDER
-------------------------------
1. COMPLETENESS CROSS-CHECK (trails_verdict/poi_verdict/elevation_verdict).
   export_trails.py and export_poi.py already gate themselves on this via
   lib/completeness.py's fail_if_incomplete() before they ever write a
   manifest - but that gate runs INSIDE the exporting script, checking
   in-memory counts it computed itself. This module re-derives the same
   answer a SECOND, independent way: read the manifest each script actually
   wrote to disk, re-hash the artifact file each manifest entry points at
   (catching a manifest that's drifted from the file - deleted, truncated,
   edited since export), and re-run the same minimum-count logic against
   what is really on disk right now, not what the exporting process
   believed it wrote before it exited. A bug in a script's own gate, or a
   bypass (the gate commented out, a stale manifest surviving a partial
   re-run), is exactly what a same-process check can never catch, because
   it is only ever checking its own belief about its own output.

2. CORRIDOR CROSS-CHECK (corridor_verdict) - the one check no single export
   script can usefully run on itself, but its real value has shifted from
   what an earlier description of this check assumed, and that is worth
   spelling out rather than silently building the wrong thing.

   The original concern this kind of check existed to catch was a STALE
   FILE: some consumer reading an old, no-longer-regenerated corridor
   (data/spike/corridor.geojson, spike_corridor.py's proof-of-concept
   output, dated 2026-07-24) while data/raw/centerline.geojson had already
   moved on (re-fetched 2026-07-25). lib/corridor.py's build_corridor() was
   extracted specifically so nothing in the real pipeline reads that stale
   file any more - export_poi.py, export_trails.py and the raster build's
   compute-cells step all build the corridor fresh, from centerline.geojson
   (see lib/corridor.py's own docstring). So the exact bug this check was
   first imagined to catch is now structurally impossible: there is no
   longer a stale committed corridor file left in the pipeline for anything
   to accidentally read.

   That changes what a corridor check run here can still usefully do. None
   of the three consumers PERSISTS the corridor it builds - each builds it
   into an in-memory DuckDB table, clips its own output against it, and
   discards it when the process exits. Nothing is saved anywhere - not in a
   manifest, not in a side file - for this module to read back and compare
   against "what export_poi.py saw." The only corridor this module can ever
   compare against is one it builds itself.

   So corridor_verdict() builds the corridor twice, independently (two
   separate DuckDB connections, the same centerline.geojson path), and
   compares the two results' area and bbox. In the happy path they always
   match exactly - same code, same input file, deterministic spatial ops -
   so this is not a "does it usually pass" check, it is a "can these two
   ever legitimately disagree" check, and disagreement is real signal, not
   noise. Two things could produce it:
     - non-determinism inside build_corridor()/DuckDB's spatial aggregate
       functions (ST_Union_Agg's internal row ordering is not something
       this codebase has verified is float-output-order-independent);
     - centerline.geojson being rewritten ON DISK between the two calls -
       e.g. a concurrent fetch_all.py re-run against the same checkout,
       landing mid-way through this module's own execution.

   Named limitation, stated rather than hidden: because both calls happen
   back-to-back in this one process, this cannot catch centerline.geojson
   having already changed BETWEEN two of the earlier export scripts' own
   runs (export_poi.py's build happened minutes before export_trails.py's,
   which happened minutes before this module even started) - only a change
   landing within this module's own brief window. Closing that wider gap
   would need each export script to persist its own corridor fingerprint
   (an area/bbox/hash) for this module to diff after the fact, which none
   of them currently do - real future work if "one script used a different
   centerline snapshot mid-run" turns out to be a live risk (e.g. a
   scheduled fetch overlapping a manual pipeline run) rather than a rare,
   mostly-theoretical race - not something to bolt on to three already-
   shipped export scripts as a rushed part of this module.

   Also asserted, independent of the two-computations-agree check: the
   corridor is not degenerate (a real, positive area). Catches a corrupted
   or truncated centerline.geojson producing a garbage-but-internally-
   consistent corridor that the two-computations-agree check alone would
   wave through - both computations would agree with each other, and both
   be wrong.

3. fetch_topo_quads.py BACKSTOP (topo_quads_verdict) - deliberately scoped
   down; see that function's own docstring for exactly what it can and
   cannot verify given the real, current manifest.json schema (it does NOT
   persist a corrupted/unmatched flag for any quad - see below).

4. DROP-VS-BASELINE DETECTION (baseline_verdict) - deliberately scoped
   down; see that function's own docstring. Baseline lives at
   data/quality_baseline.json, under the same data/ directory every other
   pipeline artifact does, so it's gitignored the same way (pipeline's
   .gitignore already excludes all of data/ - nothing extra needed here).

5. FETCH RECEIPTS (fetches_verdict) - the only check here that looks
   UPSTREAM of data/processed/, and the reason it belongs in this module
   anyway is that the four above cannot ask its question. They verify what
   the exports derived; none of them can tell whether the input an export
   derived it FROM was fetched this run or left on disk by the last one. A
   week-old input is a legitimate release and a never-fetched one is not
   (#542), and an export reading the file cannot tell those apart - only a
   record the fetcher itself left can. Staleness is printed, not failed;
   absence and drift fail.

Like check_freshness.py: pure-ish verdict functions (each does its own
I/O, but none of them mutate anything except baseline_verdict()'s eventual
write, which only main() triggers, and only on a fully-passing run), never
raises internally (see _safe_verdict below for how that promise is kept
without pretending every possible failure was anticipated), prints a
report table, returns a summary dict with a process exit code, and
sys.exit(main()) at the very bottom - the only place this module actually
exits the process.
"""

import argparse
import hashlib
import json
import sys
from enum import Enum
from pathlib import Path

import duckdb
import rasterio

from lib import fetch_receipts
from lib.completeness import count_problems
from lib.corridor import GEOGRAPHIC_CRS, METERS_PER_MILE, PROJECTED_CRS, build_corridor
from lib.poi_schema import POI_TYPES

ROOT = Path(__file__).parent
PROCESSED_DIR = ROOT / "data" / "processed"
#: Marks the one verdict an --optional run is allowed to excuse: the manifest
#: was not there at all, so this artifact was never built. Set structurally by
#: the verdict functions rather than sniffed out of the problem text, because
#: the text is not distinctive enough to carry the decision - artifact_problems()
#: says "file missing on disk" for a manifest that IS present whose artifact has
#: gone, which is the opposite situation and must never be excused.
MANIFEST_MISSING = "manifest-missing"

TRAILS_MANIFEST = PROCESSED_DIR / "trails_manifest.json"
POI_MANIFEST = PROCESSED_DIR / "poi" / "manifest.json"
ELEVATION_MANIFEST = PROCESSED_DIR / "elevation_manifest.json"
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
TOPO_QUADS_MANIFEST = ROOT / "data" / "raw" / "topo_quads" / "manifest.json"
BASELINE_PATH = ROOT / "data" / "quality_baseline.json"
#: The directory fetch receipts record their output paths relative to - the
#: pipeline root itself, not a file under it, because a receipt names several
#: outputs across data/raw/ and data/processed/. A constant like the manifest
#: paths above so a test can point the check at a tmp tree the same way.
RECEIPTS_ROOT = ROOT

# How far apart two independently-fresh corridor builds are allowed to be
# before that counts as "disagree" rather than float noise - see
# corridor_verdict(). Tight enough that a genuinely different input
# geometry (kilometers of bbox shift, sq-mi-scale area change) trips it
# immediately, loose enough to absorb ordinary floating point noise.
AREA_RELATIVE_TOLERANCE = 1e-6
BBOX_ABSOLUTE_TOLERANCE_DEG = 1e-6

# ~10% per this check's own design brief - a round starting number, not one
# derived from measured run-to-run variance (there is no history yet; this
# module is what starts building it, via data/quality_baseline.json).
# Revisit once real runs give this a measured basis, the same way
# SAMPLE_INTERVAL_METERS/etc. elsewhere in this pipeline are backed by real
# measurements rather than guesses.
# Defined in lib/completeness.py so a reader without DuckDB can have it too
# (#514). Imported rather than redefined - one home, two readers.
from lib.completeness import DROP_THRESHOLD  # noqa: E402

# How many topo quads' readability gets re-checked per run - see
# topo_readability_sample(). Same order of magnitude as check_freshness.py's
# own TOPO_SAMPLE_SIZE, for the same reason: a full re-validation of ~1,650
# quads is real, non-trivial work (spike_raster_mosaic.py's job, already),
# not something to silently duplicate on every pre-publish run.
TOPO_READABILITY_SAMPLE_SIZE = 25


class Verdict(str, Enum):
    OK = "ok"
    PROBLEM = "problem"
    SKIPPED = "skipped"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path) -> dict | None:
    """Load a JSON manifest, or None if it hasn't been written yet.

    A present-but-not-valid-JSON file is deliberately left to raise here
    rather than folded into the same None return as "missing" - those are
    different problems worth different messages. What keeps that raise from
    taking the whole run down is _safe_verdict(), one layer up, not a
    swallowed exception here."""
    if not path.exists():
        return None
    return json.loads(path.read_text())


def artifact_problems(name: str, entry: dict) -> list[str]:
    """Re-verify ONE manifest artifact entry ({"path", "sha256", ...})
    against the real file on disk right now, independent of whatever the
    exporting script itself already checked at write time. Three distinct
    things can be wrong, each its own named problem:
      - the manifest entry has no path at all (a malformed manifest);
      - the file the manifest points at no longer exists;
      - the file's content no longer matches the hash the manifest
        recorded (silent corruption/truncation/edit since export).
    Feature/point-count minimums are checked separately by callers, via
    lib/completeness.py's count_problems() - this function only verifies
    the artifact ITSELF is what the manifest claims it is."""
    path_str = entry.get("path")
    if not path_str:
        return [f"{name}: manifest entry has no path"]

    path = Path(path_str)
    if not path.exists():
        return [f"{name}: file missing on disk ({path})"]

    actual_hash = sha256_file(path)
    recorded_hash = entry.get("sha256")
    if actual_hash != recorded_hash:
        return [f"{name}: sha256 mismatch - manifest says {recorded_hash!r}, file on disk hashes to {actual_hash!r}"]

    return []


def summarise(reports: list[dict]) -> dict:
    """Roll every check's verdict into one pass/fail answer plus a process
    exit code - mirrors check_freshness.py's summarise(). SKIPPED never
    gates the exit code (nothing was produced yet for this check to
    evaluate - a different situation from evaluating something and finding
    it wrong); PROBLEM always does."""
    problems_by_check = {r["check"]: r["problems"] for r in reports if r["verdict"] is Verdict.PROBLEM}
    skipped = [r["check"] for r in reports if r["verdict"] is Verdict.SKIPPED]

    return {
        "failed_checks": sorted(problems_by_check),
        "problems": problems_by_check,
        "skipped": skipped,
        "exit_code": 0 if not problems_by_check else 1,
    }


# --- Check 1: completeness cross-check --------------------------------------


def trails_verdict(manifest_path: Path | None = None) -> dict:
    """Re-derive export_trails.py's own completeness gate from what is
    actually on disk right now - see the module docstring's check #1
    section. Independent of export_trails.py's in-process
    fail_if_incomplete() call: this reads trails_manifest.json back off
    disk and re-hashes the artifact it points at, rather than trusting
    either the manifest's self-reported numbers or export_trails.py's own
    already-exited-0 belief that its output was fine."""
    if manifest_path is None:
        manifest_path = TRAILS_MANIFEST

    manifest = read_manifest(manifest_path)
    if manifest is None:
        problem = "trails_manifest.json missing - export_trails.py may not have run"
        return {
            "check": "trails",
            "verdict": Verdict.PROBLEM,
            "detail": problem,
            "problems": [problem],
            "counts": {},
            "reason": MANIFEST_MISSING,
        }

    problems: list[str] = []
    kind_counts: dict[str, int] = {}
    for kind in ("geojson", "fgb"):
        entry = manifest.get(kind)
        if entry is None:
            problems.append(f"trails.{kind}: missing from manifest")
            continue
        problems += artifact_problems(f"trails.{kind}", entry)
        kind_counts[kind] = entry.get("feature_count", 0)

    if "geojson" in kind_counts and "fgb" in kind_counts and kind_counts["geojson"] != kind_counts["fgb"]:
        problems.append(f"trails: geojson/fgb feature_count disagree ({kind_counts['geojson']} vs {kind_counts['fgb']})")

    feature_count = kind_counts.get("geojson", kind_counts.get("fgb", 0))
    problems += count_problems({"trails": feature_count})

    verdict = Verdict.PROBLEM if problems else Verdict.OK
    detail = f"{len(problems)} problem(s)" if problems else f"{feature_count} features"
    return {
        "check": "trails",
        "verdict": verdict,
        "detail": detail,
        "problems": problems,
        "counts": {"trails": feature_count},
    }


def poi_verdict(manifest_path: Path | None = None) -> dict:
    """Re-derive export_poi.py's own per-poi_type completeness gate from
    what is actually on disk right now - see the module docstring's check
    #1 section. `crossing` is excepted from the non-zero requirement,
    mirroring export_poi.py's own minimums={"crossing": 0} override (see
    that script's module docstring: there is no NHD-crossing fetch script
    yet, so an empty-but-present crossing layer is the intentional, honest
    state, not a bug)."""
    if manifest_path is None:
        manifest_path = POI_MANIFEST

    manifest = read_manifest(manifest_path)
    if manifest is None:
        problem = "poi/manifest.json missing - export_poi.py may not have run"
        return {
            "check": "poi",
            "verdict": Verdict.PROBLEM,
            "detail": problem,
            "problems": [problem],
            "counts": {},
            "reason": MANIFEST_MISSING,
        }

    problems: list[str] = []
    counts: dict[str, int] = {}
    for poi_type in POI_TYPES:
        entry = manifest.get(poi_type)
        if entry is None:
            problems.append(f"poi.{poi_type}: missing from manifest")
            counts[f"poi:{poi_type}"] = 0
            continue

        kind_counts: dict[str, int] = {}
        for kind in ("geojson", "fgb"):
            artifact = entry.get(kind)
            if artifact is None:
                problems.append(f"poi.{poi_type}.{kind}: missing from manifest")
                continue
            problems += artifact_problems(f"poi.{poi_type}.{kind}", artifact)
            kind_counts[kind] = artifact.get("feature_count", 0)

        if "geojson" in kind_counts and "fgb" in kind_counts and kind_counts["geojson"] != kind_counts["fgb"]:
            problems.append(
                f"poi.{poi_type}: geojson/fgb feature_count disagree ({kind_counts['geojson']} vs {kind_counts['fgb']})"
            )
        counts[f"poi:{poi_type}"] = kind_counts.get("geojson", kind_counts.get("fgb", 0))

    problems += count_problems(counts, minimums={"poi:crossing": 0})

    verdict = Verdict.PROBLEM if problems else Verdict.OK
    detail = f"{len(problems)} problem(s)" if problems else f"{sum(counts.values())} features across {len(POI_TYPES)} poi_types"
    return {"check": "poi", "verdict": verdict, "detail": detail, "problems": problems, "counts": counts}


def elevation_verdict(manifest_path: Path | None = None) -> dict:
    """Re-derive a completeness signal for export_elevation.py's output
    from what is actually on disk right now. Unlike trails/poi, this is not
    a SECOND check behind export_elevation.py's own gate - that script has
    no fail_if_incomplete() call of its own yet (its module docstring: full
    runs are intentionally manual-only, see TESTING.md) - so this is the
    first automated completeness check this artifact gets. Built the same
    way as trails/poi's checks anyway, for consistency: re-hash the
    artifact, require a non-zero point_count.

    export_elevation.py's manifest is flat (path/sha256 at the top level,
    not nested under "geojson"/"fgb" like trails/poi) since it has exactly
    one output artifact - see that script's module docstring."""
    if manifest_path is None:
        manifest_path = ELEVATION_MANIFEST

    manifest = read_manifest(manifest_path)
    if manifest is None:
        problem = "elevation_manifest.json missing - export_elevation.py may not have run"
        return {
            "check": "elevation",
            "verdict": Verdict.PROBLEM,
            "detail": problem,
            "problems": [problem],
            "counts": {},
            "reason": MANIFEST_MISSING,
        }

    problems = artifact_problems("elevation_profile.json", manifest)
    point_count = manifest.get("point_count", 0)
    problems += count_problems({"elevation": point_count})

    verdict = Verdict.PROBLEM if problems else Verdict.OK
    if problems:
        detail = f"{len(problems)} problem(s)"
    else:
        detail = f"{point_count} points"
        null_pct = manifest.get("null_elevation_pct")
        if null_pct is not None:
            # Informational only, not gated: null_elevation_pct only just
            # started being recorded (see module docstring), so there is no
            # established "normal" figure yet to compare against - a
            # threshold here would be a guess dressed up as a check. It is
            # still surfaced in every report line, and check #4's baseline
            # comparison will start noticing a large swing in the absolute
            # point_count (not this percentage) once a baseline exists.
            detail += f", {null_pct}% null elevation"

    return {
        "check": "elevation",
        "verdict": verdict,
        "detail": detail,
        "problems": problems,
        "counts": {"elevation": point_count},
    }


# --- Check 2: corridor cross-check ------------------------------------------


def corridor_stats(centerline_path: Path) -> dict:
    """One fresh, independent build_corridor() call's area (sq mi) and
    bbox, from a brand-new DuckDB connection - see corridor_verdict() for
    why two of these get compared instead of trusting one."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    try:
        build_corridor(con, centerline_path)
        area_sq_mi, xmin, ymin, xmax, ymax = con.execute(f"""
            SELECT
                ST_Area(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true))
                    / {METERS_PER_MILE * METERS_PER_MILE},
                ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)
            FROM corridor
        """).fetchone()
    finally:
        con.close()
    return {"area_sq_mi": area_sq_mi, "bbox": (xmin, ymin, xmax, ymax)}


def corridor_verdict(centerline_path: Path | None = None) -> dict:
    """See the module docstring's check #2 section for the full reasoning
    behind why this compares two fresh builds against each other rather
    than one fresh build against a persisted value (nothing persists a
    corridor for this to read back). Requires both a plausible
    (non-degenerate) result and agreement between the two independent
    builds."""
    if centerline_path is None:
        centerline_path = CENTERLINE_PATH

    if not centerline_path.exists():
        problem = "centerline.geojson missing - cannot verify the corridor"
        return {"check": "corridor", "verdict": Verdict.PROBLEM, "detail": problem, "problems": [problem], "counts": {}}

    try:
        first = corridor_stats(centerline_path)
        second = corridor_stats(centerline_path)
    except Exception as exc:
        problem = f"corridor build failed: {exc!r}"
        return {"check": "corridor", "verdict": Verdict.PROBLEM, "detail": problem, "problems": [problem], "counts": {}}

    problems: list[str] = []
    area_a, area_b = first["area_sq_mi"], second["area_sq_mi"]

    if area_a is None or area_a != area_a or area_a <= 0:  # None, NaN, or non-positive
        problems.append(f"corridor: degenerate/empty geometry (area {area_a} sq mi) - check centerline.geojson")
    else:
        area_rel_diff = abs(area_a - area_b) / area_a if area_b is not None else float("inf")
        if area_rel_diff > AREA_RELATIVE_TOLERANCE:
            problems.append(
                f"corridor: two independent fresh builds from the same centerline.geojson disagree on area "
                f"({area_a:.4f} vs {area_b:.4f} sq mi) - either build_corridor() is non-deterministic or "
                "centerline.geojson changed mid-run"
            )
        for label, a, b in zip(("xmin", "ymin", "xmax", "ymax"), first["bbox"], second["bbox"]):
            if a is None or b is None or abs(a - b) > BBOX_ABSOLUTE_TOLERANCE_DEG:
                problems.append(f"corridor: two independent fresh builds disagree on bbox {label} ({a} vs {b})")

    verdict = Verdict.PROBLEM if problems else Verdict.OK
    detail = f"{len(problems)} problem(s)" if problems else f"{area_a:,.0f} sq mi"
    return {"check": "corridor", "verdict": verdict, "detail": detail, "problems": problems, "counts": {}}


# --- Check 3: fetch_topo_quads.py backstop ----------------------------------


def _resolve_topo_local_path(local_path: str) -> Path:
    """fetch_topo_quads.py stores local_path relative to ROOT when
    possible, falling back to absolute only when out_dir isn't under ROOT
    (see fetch_one_quad()'s own docstring) - handle both without assuming
    which one a given manifest used."""
    path = Path(local_path)
    return path if path.is_absolute() else ROOT / path


def _quad_is_readable(path: Path) -> bool:
    """The exact post-download validation fetch_one_quad() itself runs
    (rasterio.open + a full band-1 read) - re-run here, now, on a file that
    already passed this same check once at download time, to catch
    corruption that happened AFTER that (disk fault, an interrupted copy,
    whatever) rather than corruption fetch_topo_quads.py's own gate would
    already have caught."""
    try:
        with rasterio.open(path) as src:
            src.read(1)
        return True
    except Exception:
        return False


def topo_readability_sample(manifest: dict, size: int | None = None) -> list[str]:
    """`size` manifest URLs, evenly spread across the full sorted key list
    rather than a flat `sorted(manifest)[:size]` prefix. Manifest keys are
    full S3 URLs of the form `.../GeoTIFF/<STATE>/<file>` - the same shape
    check_freshness.py's topo_sample() documents - so a flat prefix slice
    would suffer the identical always-the-alphabetically-first-state bug
    that function exists to fix. A fixed stride across the sorted list is a
    lighter fix than that function's full state-aware seeded round-robin -
    appropriate here since this is a LOCAL readability spot-check (no per-
    request network cost to weigh, no day-to-day upstream-release timing to
    catch), not a repeat of that module's own sampling logic.

    `size` resolves TOPO_READABILITY_SAMPLE_SIZE inside the function body
    via a None sentinel, not as a plain `=TOPO_READABILITY_SAMPLE_SIZE`
    signature default - a plain default is bound once at import time and
    would silently stop responding to
    monkeypatch.setattr(module, "TOPO_READABILITY_SAMPLE_SIZE", ...)."""
    if size is None:
        size = TOPO_READABILITY_SAMPLE_SIZE

    urls = sorted(manifest)
    if size <= 0 or not urls:
        return []
    if size >= len(urls):
        return urls

    step = len(urls) / size
    return [urls[int(i * step)] for i in range(size)]


def topo_quads_verdict(manifest_path: Path | None = None, sample_size: int | None = None) -> dict:
    """Independent backstop for fetch_topo_quads.py's own now-gated
    exit-code check (completeness_problems() there already fails the run on
    any corrupted count). Deliberately scoped down from what a first read of
    "re-derive whether any quads are flagged corrupted/unmatched" might
    suggest - see the long comment below for why, and the module's final
    report for this being a named scope-down, not a silent gap.

    fetch_topo_quads.py's manifest.json (this function's real input) does
    NOT persist a corrupted or unmatched flag for any quad - not on the real
    production file, and not in the source that writes it. Read
    fetch_topo_quads.py's own fetch_one_quad(): it returns a status dict
    with "corrupted"/"unmatched"/"skipped"/"downloaded", but only mutates
    `manifest[tif_url] = {...}` on the "downloaded" branch. A quad that
    fails is reported (printed) and counted (feeding
    completeness_problems()'s exit-code gate) entirely in-memory, for that
    one run, and never written to disk anywhere. So there is no
    corrupted/unmatched flag sitting in manifest.json for a later,
    independent process to read back - that information simply does not
    outlive the run that discovered it.

    Given that, this backstop does the most useful INDEPENDENT thing that
    actually is possible from what's on disk right now:
      - every manifest-recorded quad's local_path must still exist (cheap,
        checked for all of them - catches a quad recorded as fetched that
        has since been deleted or moved);
      - a SAMPLE of them (see topo_readability_sample) must still pass the
        same rasterio-read validation fetch_one_quad() ran once, at
        download time - catching corruption that happened to the file
        AFTER that check passed, which the original gate structurally
        cannot re-detect since it only ever ran once. Sampled, not
        exhaustive: a full re-validation of ~1,650 quads is
        spike_raster_mosaic.py's own already-existing full-band pass (see
        README.md), and repeating that here on every pre-publish run would
        duplicate real, non-trivial work rather than adding a cheap
        backstop.

    Missing manifest.json (fetch_topo_quads.py, a FETCH-stage script, never
    ran) is reported SKIPPED, not PROBLEM - unlike trails/poi/elevation,
    this module's documented position in the pipeline (after the four
    EXPORT scripts) does not guarantee a fetch-stage manifest exists by the
    time this runs, and the raster archives' real inputs are the rendered
    per-cell artifacts (render_cell_tiles.py), not this manifest
    directly."""
    if manifest_path is None:
        manifest_path = TOPO_QUADS_MANIFEST

    manifest = read_manifest(manifest_path)
    if manifest is None:
        detail = "topo_quads manifest.json not present - fetch_topo_quads.py may not have run"
        return {"check": "topo_quads", "verdict": Verdict.SKIPPED, "detail": detail, "problems": [], "counts": {}}

    problems: list[str] = []
    missing = {url for url, entry in manifest.items() if not _resolve_topo_local_path(entry.get("local_path", "")).exists()}
    if missing:
        example = sorted(missing)[0]
        problems.append(f"{len(missing)} of {len(manifest)} manifest-recorded quad(s) missing from disk (e.g. {example})")

    sample = topo_readability_sample(manifest, sample_size)
    unreadable = [
        url
        for url in sample
        if url not in missing and not _quad_is_readable(_resolve_topo_local_path(manifest[url]["local_path"]))
    ]
    if unreadable:
        problems.append(
            f"{len(unreadable)} of {len(sample)} sampled quad(s) failed a readability re-check "
            f"(e.g. {unreadable[0]}) - run fix_corrupted_quads.py"
        )

    verdict = Verdict.PROBLEM if problems else Verdict.OK
    if problems:
        detail = f"{len(problems)} problem(s)"
    else:
        detail = f"{len(manifest)} quads recorded, {len(sample)} sampled for readability"
    return {"check": "topo_quads", "verdict": verdict, "detail": detail, "problems": problems, "counts": {}}


# --- Check 4: drop-vs-baseline detection ------------------------------------

# Best-effort mapping from a tracked count name to the check_freshness.py
# source key(s) whose "changed" verdict could plausibly explain a drop in
# it - see export_poi.py's/export_trails.py's own module docstrings for
# which upstream source feeds which output. Deliberately not exhaustive
# precision (e.g. it does not distinguish "communities.geojson changed"
# from "shelters.geojson changed" - both are just "atc") - see
# baseline_verdict()'s docstring for why that coarseness is the right
# direction to round in.
COUNT_UPSTREAM_SOURCES: dict[str, frozenset[str]] = {
    "trails": frozenset({"atc"}),  # centerline + side_trails
    "poi:shelter": frozenset({"atc"}),
    "poi:campsite": frozenset({"atc"}),
    "poi:resupply": frozenset({"atc", "opentrail"}),  # communities.geojson + opentrail "r" tag
    # opentrail "w"/"s" tags + osm_water.geojson, plus the members
    # export_poi.py synthesizes from ATC's CSI distances (#694) - those ride
    # the shelters/campsites layers, so an ATC change can move this count
    # too. "osm" is deliberately NOT a key here: the OSM source has no
    # check_freshness.py entry (Geofabrik republishes daily, so "changed"
    # would always be true - see fetch_osm_water.py), which means no
    # --changed-source flag can ever name it and a water-count drop on the
    # OSM side always reaches a human. An OSM mass-deletion near the trail
    # is exactly the drop somebody should look at rather than wave through.
    "poi:water": frozenset({"opentrail", "atc"}),
    "poi:crossing": frozenset(),  # always 0 today; see module docstring
    "elevation": frozenset({"elevation"}),
}


def load_baseline(path: Path | None = None) -> dict | None:
    if path is None:
        path = BASELINE_PATH
    if not path.exists():
        return None
    return json.loads(path.read_text()).get("counts", {})


def save_baseline(counts: dict, path: Path | None = None) -> None:
    """Record this run's counts, MERGED over whatever the last run recorded
    rather than replacing it.

    Merged because a run does not necessarily rebuild everything. --optional
    lets a partial run pass without an artifact it was never meant to
    produce, and a skipped check contributes no counts - so a plain
    overwrite would drop that artifact's entry from the baseline entirely.
    flag_drops() only compares names present in BOTH sides, so the next full
    run would then have nothing to compare its elevation against and would
    wave through any drop at all, however total. The baseline is meant to be
    the last KNOWN-GOOD figure, and a run that didn't look is not evidence
    the figure changed.

    Before --optional existed this was safe by accident: a missing manifest
    was a PROBLEM, so the run exited non-zero and never reached this
    function. Making partial runs pass is exactly what removed that
    protection.

    A stale entry left behind by a retired artifact is harmless in the other
    direction, for the same reason - absent from `current`, it is never
    compared."""
    if path is None:
        path = BASELINE_PATH
    merged = {**(load_baseline(path) or {}), **counts}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"counts": merged}, indent=2))


def flag_drops(
    current: dict, baseline: dict, changed_sources: set[str] | None = None, threshold: float | None = None
) -> list[str]:
    """Problem strings for any name present in both `current` and
    `baseline` whose count dropped by more than `threshold` (a None
    sentinel resolving to DROP_THRESHOLD inside the body, not a plain
    signature default - see topo_readability_sample()'s docstring for why),
    UNLESS `changed_sources` names an upstream source COUNT_UPSTREAM_SOURCES
    says could explain a drop in that name.

    A name in `baseline` but absent from `current` is not flagged here - a
    manifest that is entirely missing is already its own PROBLEM from
    trails_verdict()/poi_verdict()/elevation_verdict() directly, and
    reporting it a second time here as a "100% drop" would just be noise
    restating the same fact. A name with a zero baseline is skipped too
    (nothing meaningful to compute a percentage drop against)."""
    if changed_sources is None:
        changed_sources = set()
    if threshold is None:
        threshold = DROP_THRESHOLD

    problems = []
    for name, prior in baseline.items():
        if not prior or name not in current:
            continue
        now = current[name]
        drop = (prior - now) / prior
        if drop <= threshold:
            continue
        if COUNT_UPSTREAM_SOURCES.get(name, frozenset()) & changed_sources:
            continue
        problems.append(
            f"{name}: dropped {drop * 100:.1f}% since the last known-good run ({prior} -> {now}) with no "
            "matching check_freshness.py upstream change to explain it"
        )
    return problems


def baseline_verdict(current_counts: dict, baseline_path: Path | None = None, changed_sources: set[str] | None = None) -> dict:
    """Compare `current_counts` (this run's trails/poi/elevation counts)
    against the last known-good run recorded in data/quality_baseline.json.

    Deliberately does NOT call check_freshness.py itself to obtain
    `changed_sources` - that would make this module's own success depend on
    live upstream network availability (check_freshness.py's checks are
    individually "cheap", per that module's docstring, but a gate standing
    directly in front of publish.py should not need the network at all to
    finish), and would silently re-run check_freshness.py's own already-
    scheduled job a second time on every pre-publish run. `changed_sources`
    defaults to empty (conservative: a real drop with an innocent upstream
    explanation still gets flagged rather than silently passed through) and
    is accepted as a plain parameter instead, so a caller that already has a
    fresh check_freshness.check_all() report on hand (e.g. an orchestration
    script that runs both in sequence) can pass in the STALE source names
    itself - see check_all()'s own `changed_sources` parameter."""
    baseline = load_baseline(baseline_path)
    if baseline is None:
        detail = "no baseline yet - recorded after this run, if everything else passes"
        return {"check": "baseline", "verdict": Verdict.SKIPPED, "detail": detail, "problems": [], "counts": {}}

    problems = flag_drops(current_counts, baseline, changed_sources)
    verdict = Verdict.PROBLEM if problems else Verdict.OK
    detail = f"{len(problems)} unexplained drop(s)" if problems else "no unexplained drops vs. the last known-good run"
    return {"check": "baseline", "verdict": verdict, "detail": detail, "problems": problems, "counts": {}}


# --- Orchestration -----------------------------------------------------------


# --- Check 5: fetch receipts (#542) -----------------------------------------


def fetches_verdict(fetched: set[str] | None = None, root: Path | None = None) -> dict:
    """Did the fetchers this run depended on actually finish, and do the
    files they left behind still hash to what they said?

    The other four checks all ask about `data/processed/` - what the exports
    derived. This one asks the question one layer upstream, and it is the
    only place the answer exists: a fetcher that never ran leaves an export
    reading whatever the last run left on disk, which is a legitimate release
    if that data is a week old and not one at all if it was never fetched.
    #542 names telling those two apart as the thing packaging has to do, and
    without a receipt there is nothing to tell them apart WITH - an export
    cannot distinguish a stale input from a current one by looking at it.

    Staleness is reported, never failed. "A release built while
    poi_images.json is a week old is a legitimate release" is the issue's own
    wording; the age goes in `detail` so a reader can judge it, and only an
    absent or drifted receipt is a problem.
    """
    root = RECEIPTS_ROOT if root is None else root
    expected = fetch_receipts.expected_fetchers(sorted(fetched or ()))
    problems: list[str] = []
    ages: list[str] = []

    for name in expected + [f for f in fetch_receipts.ADVISORY_FETCHERS if f not in expected]:
        advisory = name in fetch_receipts.ADVISORY_FETCHERS
        try:
            receipt = fetch_receipts.load(name, root=root)
        except json.JSONDecodeError as exc:
            # Never excused, advisory or not. A corrupt receipt is not the
            # same as a fetch that did not happen - something wrote a
            # half-file where a completion record belongs, and packaging
            # should stop rather than guess which.
            problems.append(f"{name}: receipt is not readable JSON ({exc})")
            continue

        if receipt is None:
            if advisory:
                ages.append(f"{name} never")
            else:
                problems.append(f"{name}: no receipt - this run needs it and it never finished")
            continue

        problems.extend(fetch_receipts.verify(receipt, root=root))
        days = fetch_receipts.age_days(receipt)
        ages.append(f"{name} {'?' if days is None else f'{days:.1f}d'}")

    verdict = Verdict.PROBLEM if problems else Verdict.OK
    detail = f"{len(expected)} required fetch(es); ages: {', '.join(ages) if ages else 'none recorded'}"
    return {"check": "fetches", "verdict": verdict, "detail": detail, "problems": problems, "counts": {}}


def _safe_verdict(check_name: str, fn) -> dict:
    """Run one verdict-building function and never let it take check_all()
    down with it.

    check_freshness.py earns its "never raises" property by catching each
    specific failure mode where it can occur (a bad HTTP response, a JSON
    field that failed to parse). This module does the same at each specific
    point it can anticipate (corridor_verdict()'s own try/except around the
    corridor build, _quad_is_readable()'s around rasterio) but also wraps
    the whole verdict function here, one level up. That extra layer matters
    specifically for this module in a way it didn't for check_freshness.py:
    this is a gate standing directly in front of publish.py, so a crash
    here must never be mistaken by whatever invokes this pipeline for
    "nothing to report" - it becomes its own PROBLEM instead, loud and
    failing, rather than an unhandled traceback an orchestration script
    might not even notice."""
    try:
        return fn()
    except Exception as exc:
        problem = f"{check_name} check crashed: {exc!r}"
        return {"check": check_name, "verdict": Verdict.PROBLEM, "detail": problem, "problems": [problem], "counts": {}}


def as_optional(report: dict) -> dict:
    """Downgrade a "never built" PROBLEM to SKIPPED, for a run that was
    never meant to produce that artifact in the first place.

    Only that case. A manifest that exists and fails its checks stays a
    PROBLEM however this is called - "I did not build it" and "I built it
    and it is wrong" are different answers, and only the first is
    excusable.

    This exists because publish.py already supports partial publishes
    ("a fresh checkout that's only run some export scripts still publishes
    what it has", collect_artifacts()), so a gate standing in front of it
    that insists on a full set contradicts the thing it is gating. Made
    explicit per-run rather than inferred, so a full run that silently
    loses its elevation export still fails loudly."""
    if report["verdict"] is not Verdict.PROBLEM:
        return report
    if report.get("reason") != MANIFEST_MISSING:
        return report

    return {**report, "verdict": Verdict.SKIPPED, "problems": []}


def check_all(
    changed_sources: set[str] | None = None,
    optional: set[str] | None = None,
    fetched: set[str] | None = None,
) -> list[dict]:
    """Every check's verdict, in the priority order the module docstring
    lays out. Never raises - see _safe_verdict()."""
    if optional is None:
        optional = set()

    def verdict(name: str, fn) -> dict:
        report = _safe_verdict(name, fn)
        return as_optional(report) if name in optional else report

    trails = verdict("trails", trails_verdict)
    poi = verdict("poi", poi_verdict)
    elevation = verdict("elevation", elevation_verdict)
    corridor = _safe_verdict("corridor", corridor_verdict)
    topo_quads = _safe_verdict("topo_quads", topo_quads_verdict)

    current_counts = {**trails["counts"], **poi["counts"], **elevation["counts"]}
    baseline = _safe_verdict("baseline", lambda: baseline_verdict(current_counts, changed_sources=changed_sources))
    # Deliberately NOT routed through as_optional(). Its excuse is keyed on
    # MANIFEST_MISSING - "this artifact was never built" - and the fetches
    # check has the opposite polarity: a missing receipt is the whole finding,
    # not a reason to look away. Which fetchers this run needed is said with
    # --fetched instead.
    fetches = _safe_verdict("fetches", lambda: fetches_verdict(fetched=fetched, root=RECEIPTS_ROOT))

    return [trails, poi, elevation, corridor, topo_quads, baseline, fetches]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Note the deviation from argparse's own convention: `argv=None` means
    "no arguments", NOT "read sys.argv". The real entry point passes
    sys.argv[1:] explicitly instead. Falling back to sys.argv would make a
    bare main() pick up whatever argv the surrounding process happened to
    have - under pytest that is pytest's own flags, and every existing
    main() test fails with "unrecognized arguments"."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--changed-source",
        action="append",
        default=[],
        metavar="NAME",
        dest="changed_sources",
        help=(
            "An upstream source check_freshness.py reported as STALE, repeatable. "
            "A count drop is only flagged if no source that feeds it changed - so "
            "without this, a legitimate drop caused by an upstream change is "
            "reported as unexplained. Passed in rather than looked up, so this "
            "gate never needs the network; see baseline_verdict()."
        ),
    )
    parser.add_argument(
        "--optional",
        action="append",
        default=[],
        metavar="CHECK",
        choices=["trails", "poi", "elevation"],
        dest="optional",
        help=(
            "An artifact this run was not meant to produce, repeatable. Its "
            "manifest being absent reports SKIPPED instead of failing. An "
            "artifact that IS present still has to pass. Use it when "
            "deliberately publishing a subset, which publish.py supports."
        ),
    )
    parser.add_argument(
        "--fetched",
        action="append",
        default=[],
        metavar="FETCHER",
        choices=["fetch_atc_photos", "fetch_poi_images", "fetch_elevation", "fetch_osm_water"],
        dest="fetched",
        help=(
            "A conditional fetcher this run was asked to run, repeatable. Its "
            "receipt then has to be there. fetch_all and fetch_opentrail are "
            "always required and need no flag - no export can run without "
            "them. Photos and elevation are workflow inputs, so only the "
            "caller knows whether this run asked for them."
        ),
    )
    return parser.parse_args([] if argv is None else argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    reports = check_all(
        changed_sources=set(args.changed_sources),
        optional=set(args.optional),
        fetched=set(args.fetched),
    )
    for report in reports:
        print(f"  {report['verdict'].value.upper():8} {report['check']:12} {report['detail']}")

    summary = summarise(reports)
    for check in summary["failed_checks"]:
        print(f"\n{check}:")
        for problem in summary["problems"][check]:
            print(f"  {problem}")
    if summary["skipped"]:
        print(f"\nNothing to check yet: {', '.join(summary['skipped'])}")

    if summary["exit_code"] == 0:
        current_counts = {k: v for r in reports for k, v in r["counts"].items()}
        save_baseline(current_counts)
        print(f"\nAll output-quality checks passed. Baseline recorded -> {BASELINE_PATH}")
    else:
        print(f"\nFailed: {', '.join(summary['failed_checks'])}")

    return summary["exit_code"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
