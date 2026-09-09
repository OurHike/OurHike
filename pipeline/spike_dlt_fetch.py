"""Port the ArcGIS fetch to dlt and count what it actually replaces — the one
`@unvalidated` item #1294 left open, run rather than estimated.

**#1294 — Evaluated and declined: dlt for the fetch layer, and a weekly cadence
for non-alert data** declined dlt on five reasons and then said plainly which
part of it nobody had checked:

> **@unvalidated:** the ~1,000-1,200 line estimate of what dlt would replace is
> read off the module boundaries listed above, not from a spike. Nobody has
> written the ArcGIS source and measured it. What would settle it: a throwaway
> branch porting `fetch_all.py` alone and counting.

This is that branch, kept rather than thrown away because the numbers turned
out to correct the issue in both directions. Run 2026-09-09 against the live
ATC centerline FeatureServer with dlt 1.30.0 on Python 3.13. **The verdict does
not move — dlt is still the wrong tool for this layer — but two of the reasons
given for it were wrong, and the headline estimate was too generous to dlt by
an order of magnitude.**

## What was built

A working dlt `rest_api` source against `ANST_Centerline/FeatureServer/0`,
landing into DuckDB, in three configurations. All three fetch the same 3,025
features; what differs is what dlt does with them on the way in.

## What it measured

| configuration | tables | rows landed | wall clock |
|---|---|---|---|
| dlt defaults | **4** | **2,072,165** | 90-102 s |
| `max_table_nesting = 0` | 1 | 3,025 | 16-23 s |
| `columns={"geometry": {"data_type": "json"}}` | 1 | 3,025 | 13-14 s |
| **incumbent** `fetch_layer_to_file` | — (31.2 MB GeoJSON) | 3,025 | **7.5-11.2 s** |
| **incumbent, unchanged upstream** | — (nothing written) | — | **0.67-0.70 s** |

**Row counts are the measurement; the timings are context.** Three full runs on
2026-09-09 produced identical table shapes — 3,025 / 689,572 / 1,379,280 / 288
every time — while every wall clock moved by 20-40%, which is the network and
not the tool. The ranges above span those three runs; anything read off a
single number here would be reading noise.

**On defaults, one trail line becomes 2,072,165 rows across four tables.** dlt's
normalizer walks nested JSON into child tables, and a LineString's
`coordinates` is nested twice — so `centerline__geometry__coordinates` gets one
row per vertex (689,572) carrying no coordinate at all, just a parent id and a
list index, and `centerline__geometry__coordinates__list` gets one row per
*number* (1,379,280), longitude and latitude each landing as their own row.
`centerline__geometry__coordinates__list__list` (288) is the MultiLineString
tail. The A.T.'s shape survives only as a three-table join ordered by
`_dlt_list_idx` twice.

**It is one line of config to fix, and the fix is not discoverable from the
failure.** A `json` column hint keeps the geometry whole while letting the 52
`properties__*` columns flatten normally, and DuckDB's spatial extension reads
the result back: `ST_GeomFromGeoJSON` round-trips 3,025 features and 689,712
vertices. `max_table_nesting = 0` also works and is worse — it collapses
`properties` to a JSON blob too, giving up the 52 typed columns that are the
reason to want a warehouse.

Nothing warns you. The default run succeeds, reports `LOADED` with no failed
jobs, and produces a schema that is wrong in a way no row count would show.

## What it replaces, counted

The fetch layer, measured the same day by the counter at the bottom of this
file: **7,379 lines across 17 fetchers and 8 supporting modules, of which 3,315
are code** (blank, comment and docstring lines excluded — this repository keeps
a lot of reasoning in prose, and counting it as replaceable would flatter any
tool).

What the working dlt port demonstrably replaced, in that layer:

| incumbent | code lines | dlt's answer |
|---|---|---|
| `lib/arcgis.py`'s pagination loop | ~22 | 6 lines of paginator config |
| `lib/http_retry.py` | 98 | its own retry, on its own policy |

**That is 22 to 120 code lines of 3,315 — 0.7% to 3.6%**, against #1294's
estimated "~1,000-1,200 lines of an ~8,300-line fetching layer" (12-14%). The
estimate was reasoned off module boundaries and read whole modules as
replaceable; the port shows dlt reaching the transport inside them and nothing
else. **@measured for the ArcGIS path that was actually ported; the
extrapolation across the other 16 fetchers is by mechanism rather than by
porting each, so treat the 3.6% ceiling as the firmer end and the layer-wide
figure as reasoned.**

The 98 is bracketed rather than counted because taking it is a decision, not a
saving: `lib/http_retry.py:24-35` says the per-caller postures are deliberately
different — *"Both are right about themselves"* — and `fetch_atc_photos.py`
refuses the same merge a second time, in writing, because Wikimedia's `maxlag`
etiquette is a contract with one API rather than general politeness. A
framework with one retry policy reverses that twice.

## Two things #1294 got wrong, corrected here

**Reason 4's first half is false.** The issue expected dlt to break against
`pipeline/tests/conftest.py:115-143`'s autouse guard — *"Any dlt HTTP path that
is not `requests`-adapter-interceptable fails hard there."* Measured: a dlt
pipeline runs to completion under a verbatim reproduction of that guard, with
`requests_mock` intercepting normally and **zero** non-loopback connection
attempts. dlt's `rest_api` is built on `requests`, so the adapter layer catches
it exactly as the guard's docstring predicts for `requests_mock`.

**The Python-version cost is zero, where dbt's was not.** dlt 1.30.0 declares
`Requires-Python: >=3.10,<3.15` and classifiers through 3.14, so it runs on
CI's 3.14. `DBT.md:121` had to pin the `dbt` job to Python 3.12 deliberately;
this would need no such split.

## Three things it confirms, now measured rather than argued

**The stop condition is right by default, which was not safe to assume.**
`lib/arcgis.py:29-35` stops paginating on an *empty* page and never a short
one, with regression tests, because stopping on a short page skipped data.
dlt's `OffsetPaginator` defaults to `stop_after_empty_page=True` and reached
all 3,025 features across two pages. It does need `total_path=None` passed
explicitly — the default `total_path="total"` expects a field ArcGIS's GeoJSON
response does not carry.

**A 304 is an error to dlt, and a success to us.** `fetch_opentrail.py:74-79`
treats `If-None-Match` → 304 as this fetcher succeeding — it asked upstream and
confirmed the local copy current — and records a receipt on that path so a
skipped run does not look to packaging like a run that never fetched. Fed a
304, dlt raises `PipelineStepFailed` / `ResourceExtractionError` out of the
paginator. Expressing the skip means a custom response hook: hand-written code
again, in a less obvious place.

**The cheap pre-check has no home in dlt's model.** `get_layer_edit_date` is one
metadata request that decides whether to pay for the full fetch, and it is the
whole reason `fetch_all.py`'s docstring can call a weekly schedule cheap. It
costs **0.67-0.70 s against a 7.5-11.2 s fetch** on this layer, and on an
unchanged week it is the entire run. dlt's incremental loading keys on a cursor field inside the
rows, which is a different question asked after the transfer it exists to
avoid. Nothing stops you calling the metadata endpoint yourself and skipping
the resource — that is just the incumbent, hosted inside a framework.

## What this spike does not claim

It ports **one** ArcGIS layer. It does not port `fetch_all.py`'s completeness
gate, its manifest, or its receipts, because dlt has no view on any of them —
which is the finding, not an omission. It says nothing about the nine
file-and-GDAL sources (#1294 reason 1), which was never in question: dlt loads
rows, and a 3.5 GB Geofabrik extract is not rows.

**@unvalidated:** dlt's telemetry defaults to on (`dlthub_telemetry: True`,
endpoint `https://telemetry.scalevector.ai`), which matters because
`CONTRIBUTING.md:136` notes five workflows install these pins *"in a job
holding R2 write credentials"*. This run observed no outbound attempt under the
socket guard, so what it sends and when is unmeasured here. What would settle
it: run a pipeline with telemetry left at its default behind a logging proxy
and read what leaves. `DLT_TELEMETRY=false` is set throughout this script
regardless.

Usage — needs `pip install "dlt[duckdb]"`, deliberately not in requirements.in:

    python spike_dlt_fetch.py              # the three configurations, live
    python spike_dlt_fetch.py --count-only # just the line census, no network
"""

import argparse
import ast
import glob
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS_PATH = ROOT / "data" / "spike_dlt_fetch.json"

# ATC's centerline: 3,025 features over a maxRecordCount of 2,000, so it
# paginates, and its geometry nests twice. Both are the point.
LAYER_URL = "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Centerline/FeatureServer/0"

# The fetch layer, as counted for the "what it replaces" table above. Listed
# rather than globbed for the lib half so the census says what it counted.
SUPPORTING_MODULES = [
    "lib/arcgis.py",
    "lib/http_retry.py",
    "lib/source_registry.py",
    "lib/completeness.py",
    "lib/fetch_receipts.py",
    "lib/club_pdfs.py",
    "lib/atc_scrape.py",
    "lib/freshness_state.py",
]


def code_line_count(path: Path) -> tuple[int, int]:
    """Return (total lines, code lines) for a Python file, where code excludes
    blank lines, comment lines and docstrings. The exclusion is the point: this
    repository deliberately carries its reasoning in prose, and counting a
    docstring as something a framework could replace would flatter any tool."""
    src = path.read_text()
    docstring_lines: set[int] = set()
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if ast.get_docstring(node, clean=False) and node.body and isinstance(node.body[0], ast.Expr):
            expr = node.body[0]
            docstring_lines.update(range(expr.lineno, (expr.end_lineno or expr.lineno) + 1))

    total = code = 0
    for lineno, line in enumerate(src.splitlines(), 1):
        total += 1
        stripped = line.strip()
        if lineno in docstring_lines or not stripped or stripped.startswith("#"):
            continue
        code += 1
    return total, code


def census() -> dict:
    """Measure the fetch layer, so the percentage this spike quotes is
    reproducible rather than a number in a docstring."""
    modules = sorted(glob.glob(str(ROOT / "fetch_*.py")))
    modules += [str(ROOT / m) for m in SUPPORTING_MODULES if (ROOT / m).exists()]

    per_module = {}
    total_lines = total_code = 0
    for module in modules:
        path = Path(module)
        lines, code = code_line_count(path)
        per_module[path.relative_to(ROOT).as_posix()] = {"lines": lines, "code": code}
        total_lines += lines
        total_code += code

    return {"modules": len(modules), "lines": total_lines, "code": total_code, "per_module": per_module}


def dlt_configurations() -> list[tuple[str, dict, dict]]:
    """(label, resource overrides, notes) for the three ports, in the order the
    docstring's table reports them: what you get if you do nothing, the blunt
    knob, and the one a competent adopter would actually reach for."""
    return [
        ("defaults", {}, {"what": "dlt's own normalization, untouched"}),
        ("max_table_nesting=0", {"max_table_nesting": 0}, {"what": "no child tables, properties collapse too"}),
        (
            "geometry json hint",
            {"columns": {"geometry": {"data_type": "json"}}},
            {"what": "geometry whole, properties still flattened"},
        ),
    ]


def run_dlt_port(label: str, overrides: dict, workdir: Path) -> dict:
    """Build and run one dlt configuration against the live layer, returning the
    table/row shape it produced. Imported lazily: dlt is a parameter of this
    spike, not a dependency of the pipeline (see the usage note above)."""
    try:
        import dlt
        from dlt.sources.rest_api import rest_api_source
    except ImportError:
        print('dlt is not installed. This spike needs it: pip install "dlt[duckdb]"')
        sys.exit(2)

    resource: dict = {
        "name": "centerline",
        "endpoint": {
            "path": "query",
            "params": {"where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson"},
            "data_selector": "features",
        },
    }
    column_hints = overrides.pop("columns", None)
    if column_hints:
        resource["columns"] = column_hints

    source = rest_api_source(
        {
            "client": {
                "base_url": LAYER_URL + "/",
                "paginator": {
                    "type": "offset",
                    "limit": 1000,
                    "offset_param": "resultOffset",
                    "limit_param": "resultRecordCount",
                    # ArcGIS's GeoJSON response carries no `total`, which is
                    # this paginator's default stop signal. Without this it
                    # cannot page at all.
                    "total_path": None,
                    # Already the default, named here because it is the
                    # property lib/arcgis.py has regression tests for: stop on
                    # an EMPTY page, never a short one.
                    "stop_after_empty_page": True,
                },
            },
            "resources": [resource],
        }
    )
    for attr, value in overrides.items():
        setattr(source.centerline, attr, value)

    slug = label.replace(" ", "_").replace("=", "").replace("0", "zero")

    # The destination path is explicit because the default is the working
    # directory, and the working directory here is the repository. Left alone,
    # this spike drops 117 MB of .duckdb files into pipeline/ - which is not
    # gitignored, unlike data/, so the next `git add` publishes upstream rows
    # permanently (CONTRIBUTING.md, "Data does not go in commits"). Measured:
    # it did exactly that on the first run of this file.
    database_path = workdir / f"{slug}.duckdb"

    started = time.time()
    pipeline = dlt.pipeline(
        pipeline_name=f"spike_{slug}",
        destination=dlt.destinations.duckdb(str(database_path)),
        dataset_name="raw_spike",
        pipelines_dir=str(workdir / f"pipe_{slug}"),
    )
    pipeline.run(source)
    elapsed = time.time() - started

    import duckdb

    with duckdb.connect(str(database_path), read_only=True) as con:
        tables = con.execute(
            "select table_name from duckdb_tables() where schema_name = 'raw_spike' and table_name not like '\\_dlt%' escape '\\'"
        ).fetchall()
        shape = {}
        for (table,) in tables:
            shape[table] = con.execute(f'select count(*) from raw_spike."{table}"').fetchone()[0]
        columns = con.execute(
            "select count(*) from information_schema.columns where table_schema = 'raw_spike' and table_name = 'centerline'"
        ).fetchone()[0]

    return {
        "label": label,
        "seconds": round(elapsed, 1),
        "tables": len(shape),
        "rows": sum(shape.values()),
        "columns_on_centerline": columns,
        "shape": shape,
    }


def run_incumbent() -> dict:
    """Time what is there now, on the same layer, for the same features."""
    sys.path.insert(0, str(ROOT))
    from lib.arcgis import fetch_layer_to_file, get_layer_edit_date

    started = time.time()
    edit_date = get_layer_edit_date(LAYER_URL)
    precheck_seconds = time.time() - started

    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "centerline.geojson"
        started = time.time()
        features = fetch_layer_to_file(LAYER_URL, out_path)
        fetch_seconds = time.time() - started
        size_bytes = out_path.stat().st_size

    return {
        "precheck_seconds": round(precheck_seconds, 2),
        "data_last_edit_date": edit_date,
        "fetch_seconds": round(fetch_seconds, 1),
        "features": features,
        "geojson_bytes": size_bytes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--count-only", action="store_true", help="just the line census, no network")
    args = parser.parse_args()

    # Never phone home from a spike. The default is on; see the @unvalidated
    # note in this module's docstring for what that is worth.
    os.environ["DLT_TELEMETRY"] = "false"

    layer_census = census()
    print(f"Fetch layer: {layer_census['lines']:,} lines across {layer_census['modules']} modules, {layer_census['code']:,} code")

    results = {"census": layer_census, "layer_url": LAYER_URL}

    if not args.count_only:
        print(f"\nIncumbent, on {LAYER_URL.rsplit('/', 3)[-3]} ...")
        results["incumbent"] = run_incumbent()
        print(
            f"  pre-check {results['incumbent']['precheck_seconds']}s"
            f"  ·  full fetch {results['incumbent']['fetch_seconds']}s"
            f"  ·  {results['incumbent']['features']:,} features"
        )

        workdir = Path(tempfile.mkdtemp(prefix="spike_dlt_"))
        try:
            results["dlt"] = []
            for label, overrides, notes in dlt_configurations():
                print(f"\ndlt [{label}] ...")
                run = run_dlt_port(label, dict(overrides), workdir)
                run["notes"] = notes["what"]
                results["dlt"].append(run)
                print(f"  {run['tables']} table(s)  ·  {run['rows']:,} rows  ·  {run['seconds']}s  ·  {run['notes']}")
                for table, rows in sorted(run["shape"].items()):
                    print(f"      {table:48s} {rows:>10,}")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    # Counts and timings only - no upstream rows. data/ is gitignored, which is
    # where anything a script produces belongs (CONTRIBUTING.md).
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nResults -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
