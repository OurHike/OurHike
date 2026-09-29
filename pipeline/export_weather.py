"""Bake the fetched NBM cycle into one weather file per trail cell (#1056).

The sixth artifact family in the conditions prefix
([CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md)), and the first
that is one file per 1-degree cell rather than one file:

    conditions/weather_index.json       which cells have a forecast, and from which run
    conditions/weather/<cell>.json      the forecast for that cell's trail squares   (this)

One file per cell because a phone fetches the cells under its hike and never
all 442 (features/WEATHER.md §7); the cell is OFFLINE_COVERAGE.md's grid, so
"which weather does this phone hold" has the same answer as "which map".

WHAT A CELL FILE CARRIES, AND WHAT IT DOES NOT
----------------------------------------------
Every NBM square under that cell's trails and waypoints
(`build_weather_squares.py`, the maintainer's choice of 2026-09-24), each with
its own series for every field `fetch_weather.py` fetched, in NBM's units.
`squares[i]` is the square `fields[f]["values"][i]` belongs to, so a phone
that projects a point to its square (lib/nbm_grid.py's arithmetic, carried in
the index as `grid`) finds that point's whole forecast in one lookup.

- **No square is forecast that NBM did not forecast.** A value NBM left empty
  is `null`, never 0: "no rain chance published" and "0% chance of rain" are
  different sentences, and only one of them is true.
- **A water square says where its numbers came from.** `borrowed` lists each
  square that reads a land neighbour instead (WEATHER.md §6).
- **No elevation correction, here or in `hrrr`.** Measured, NBM corrected for
  height scored worse than NBM as published (WEATHER.md §3), so NBM's fields
  are as NOAA published them.
- **`hrrr`: the first two days' temperature, uncorrected, with the heights to
  correct it from.** The maintainer chose HRRR corrected for elevation for
  hours 1-48 (2026-09-24). The correction is the phone's to apply, because it
  needs the trail point's own height from the DEM the phone holds: HRRR's
  2 m temperature for each HRRR cell a trail point falls in, that cell's
  model `height` in metres, and the cells themselves as [row, col] on HRRR's
  grid (the index carries it as `hrrr_grid`), so the phone finds its point's
  cell by arithmetic, as it does its NBM square. Degrees Celsius to a tenth:
  GDAL's reading of HRRR's Kelvin, not converted further, and a tenth because
  rounding to whole degrees would add up to ±0.9 °F against the 2.3 °F
  accuracy that justified HRRR (measured 2026-09-29: tenths make a cell file
  28-38% bigger gzipped, whole degrees 8-12%). `hrrr` is `null` when the run
  could not fetch HRRR; the phone then uses NBM for every hour. **Nothing
  corrected reaches a hiker before step 2 re-runs the spike with the phone's
  exact arithmetic** (WEATHER.md §3).
- **No warnings, but each square's NWS zones.** The alerts themselves are
  their own artifact (`export_weather_alerts.py`). What this file adds is
  `zones[i]`: every NWS forecast zone, fire weather zone and county whose
  outline overlaps square `i`, as "<kind>/<id>" ("forecast/NHZ010"). A phone
  with signal asks NWS for exactly those zones' alerts - the maintainer's
  choice of 2026-09-26 (WEATHER.md §5) - and an empty list means NWS's
  outlines put no zone there, so the phone has nothing to ask about.

    python export_weather.py
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio

from lib import hrrr_grid, nbm_grid
from lib.atomic_write import write_text_atomically
from lib.hashing import sha256_file
from lib.manifest_paths import to_manifest_path

ROOT = Path(__file__).resolve().parent
WEATHER_RAW = ROOT / "data" / "raw" / "weather"
SQUARES_PATH = WEATHER_RAW / "squares.json"
CYCLE_PATH = WEATHER_RAW / "cycle.json"
HRRR_CYCLE_PATH = WEATHER_RAW / "hrrr_cycle.json"
CONDITIONS_DIR = ROOT / "data" / "processed" / "conditions"
CELL_DIR = CONDITIONS_DIR / "weather"
INDEX_PATH = CONDITIONS_DIR / "weather_index.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "weather_manifest.json"

# The payload name. `conditions/weather/<cell>.json` and
# `conditions/weather_index.json` are URLs deployed clients will request, and
# a key in that bucket can never be renamed (pipeline/R2_LAYOUT.md).
PAYLOAD = "weather"
INDEX_PAYLOAD = "weather_index"
SCHEMA = 1

# Each field's unit as NBM publishes it (fetch_weather.py's docstring has
# where each came from), and the range a real value can fall in. The range is
# a decode guard, not a forecast check: every bound is generous enough that
# weather cannot reach it and a misread file lands far outside it at once.
FIELDS = {
    "temp": ("F", -80, 140),
    "maxt": ("F", -80, 140),
    "mint": ("F", -80, 140),
    "pop01": ("%", 0, 100),
    "pop12": ("%", 0, 100),
    "tstm01": ("%", 0, 100),
    "sky": ("%", 0, 100),
    "windspd": ("kt", 0, 200),
    "windgust": ("kt", 0, 250),
}

CREDIT = "NOAA forecast"

HRRR_SOURCE = "NOAA High-Resolution Rapid Refresh (HRRR)"
# HRRR 2 m temperature as GDAL reads it, and the range a real one can fall in:
# a decode guard, as FIELDS' ranges are. The unit tag is checked on every
# file, because a GDAL that stopped converting would hand back Kelvin - 280
# "degrees" that this range would also catch, but the tag says why.
HRRR_UNIT_TAG = "[C]"
HRRR_TEMP_C = (-70.0, 60.0)


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_field(path: Path) -> tuple[np.ndarray, float | None]:
    """One forecast raster and its nodata value, refused if it is not on
    NBM's pinned grid."""
    with rasterio.open(path) as ds:
        if not nbm_grid.matches(ds.transform, ds.crs, ds.width, ds.height):
            raise RuntimeError(f"{path.name} is not on NBM's CONUS grid; lib/nbm_grid.py's pin no longer holds")
        return ds.read(1), ds.nodata


def sample(array: np.ndarray, nodata: float | None, rows: np.ndarray, cols: np.ndarray, field: str) -> list:
    """The values at the given squares, `None` where NBM published nothing,
    refusing any value outside the field's physical range."""
    values = array[rows, cols].astype(np.float64)
    missing = ~np.isfinite(values)
    if nodata is not None:
        missing |= values == nodata
    unit, low, high = FIELDS[field]
    present = values[~missing]
    if present.size and (present.min() < low or present.max() > high):
        raise RuntimeError(
            f"{field} read {present.min():.0f}..{present.max():.0f} {unit}, outside {low}..{high}: "
            "the file decoded wrong, and publishing it would put a plausible-looking wrong number on a card"
        )
    return [None if m else int(round(v)) for v, m in zip(values.tolist(), missing.tolist(), strict=True)]


def read_hrrr_field(path: Path) -> np.ndarray:
    """One HRRR 2 m temperature message, refused if it is not on HRRR's pinned
    grid or not in degrees Celsius."""
    with rasterio.open(path) as ds:
        if not hrrr_grid.matches(ds.transform, ds.crs, ds.width, ds.height):
            raise RuntimeError(f"{path.name} is not on HRRR's CONUS grid; lib/hrrr_grid.py's pin no longer holds")
        unit = ds.tags(1).get("GRIB_UNIT")
        if unit != HRRR_UNIT_TAG:
            raise RuntimeError(f"{path.name} reads in {unit!r}, not {HRRR_UNIT_TAG!r}; refusing to label it Celsius")
        return ds.read(1)


def bake_hrrr(squares_doc: dict, hrrr_doc: dict, raw_dir: Path) -> dict[str, dict]:
    """{cell: the `hrrr` block of that cell's file}."""
    reads = {(r, c): (rr, rc, height) for r, c, rr, rc, height in squares_doc["hrrr_reads"]}
    order = sorted(reads)
    rows = np.array([reads[cell][0] for cell in order], dtype=np.int64)
    cols = np.array([reads[cell][1] for cell in order], dtype=np.int64)
    low, high = HRRR_TEMP_C
    times, columns = [], []
    for when, relpath in hrrr_doc["fields"]["temp2m"]:
        values = read_hrrr_field(raw_dir / relpath)[rows, cols].astype(np.float64)
        present = values[np.isfinite(values)]
        if present.size and (present.min() < low or present.max() > high):
            raise RuntimeError(
                f"HRRR temperature read {present.min():.1f}..{present.max():.1f} C, outside {low:.0f}..{high:.0f}: "
                "the file decoded wrong"
            )
        times.append(when)
        columns.append([round(float(v), 1) if np.isfinite(v) else None for v in values])
    by_cell = dict(zip(order, zip(*columns, strict=True), strict=True))
    blocks = {}
    for cell, hrrr_cells in squares_doc["hrrr_cells"].items():
        listed = [tuple(c) for c in hrrr_cells]
        blocks[cell] = {
            "source": HRRR_SOURCE,
            "cycle": hrrr_doc["cycle"],
            "units": {"temp": "C", "height": "m"},
            "times": times,
            "cells": [list(c) for c in listed],
            "height": [reads[c][2] for c in listed],
            "borrowed": [[n, reads[c][0], reads[c][1]] for n, c in enumerate(listed) if reads[c][:2] != c],
            "temp": [list(by_cell[c]) for c in listed],
        }
    return blocks


def bake(
    squares_doc: dict, cycle_doc: dict, raw_dir: Path, generated_at: datetime, hrrr_doc: dict | None = None
) -> tuple[dict, dict[str, dict]]:
    """(index document, {cell: cell document}), with nothing written.
    `hrrr_doc` is fetch_hrrr.py's record, or None when HRRR was not fetched."""
    if "zones" not in squares_doc:
        raise RuntimeError("squares.json predates each square's NWS zones; rerun build_weather_squares.py")
    cells = squares_doc["cells"]
    zones_of: dict[tuple[int, int], list[str]] = {}
    for key, zone_squares in sorted(squares_doc["zones"].items()):
        for sq in zone_squares:
            zones_of.setdefault(tuple(sq), []).append(key)
    order = sorted({tuple(sq) for sq_list in cells.values() for sq in sq_list})
    position = {sq: i for i, sq in enumerate(order)}
    read_from = {tuple(water): tuple(land) for water, land in squares_doc.get("borrowed", [])}
    rows = np.array([read_from.get(sq, sq)[0] for sq in order], dtype=np.int64)
    cols = np.array([read_from.get(sq, sq)[1] for sq in order], dtype=np.int64)

    series: dict[str, dict] = {}
    for field, files in cycle_doc["fields"].items():
        if field not in FIELDS:
            raise RuntimeError(f"cycle.json carries {field}, which this export has no unit or range for")
        times, columns = [], []
        for when, relpath in files:
            array, nodata = read_field(raw_dir / relpath)
            times.append(when)
            columns.append(sample(array, nodata, rows, cols, field))
        series[field] = {"times": times, "by_square": list(zip(*columns, strict=True))}

    version = cycle_doc["version"].removeprefix("blend")
    source = f"NOAA National Blend of Models (NBM) {version}"
    common = {
        "schema": SCHEMA,
        "source": source,
        "credit": CREDIT,
        "cycle": cycle_doc["cycle"],
        "generated_at": _stamp(generated_at),
        "release": squares_doc["release"],
    }
    if hrrr_doc is not None and "hrrr_reads" not in squares_doc:
        raise RuntimeError("squares.json predates HRRR's cells; rerun build_weather_squares.py")
    hrrr = bake_hrrr(squares_doc, hrrr_doc, raw_dir) if hrrr_doc is not None else {}
    documents = {}
    for cell, cell_squares in cells.items():
        indices = [position[tuple(sq)] for sq in cell_squares]
        borrowed = [[n, *read_from[tuple(sq)]] for n, sq in enumerate(cell_squares) if tuple(sq) in read_from]
        documents[cell] = {
            "payload": PAYLOAD,
            **common,
            "cell": cell,
            "units": {field: FIELDS[field][0] for field in series},
            "squares": cell_squares,
            "zones": [zones_of.get(tuple(sq), []) for sq in cell_squares],
            "borrowed": borrowed,
            "fields": {
                field: {"times": data["times"], "values": [list(data["by_square"][i]) for i in indices]}
                for field, data in series.items()
            },
            "hrrr": hrrr.get(cell),
        }
    index = {
        "payload": INDEX_PAYLOAD,
        **common,
        "grid": squares_doc["grid"],
        "cells": {cell: {"squares": len(cells[cell])} for cell in sorted(cells)},
        "outside_grid": squares_doc.get("outside_grid", []),
        "water_kept": squares_doc.get("water_kept", []),
        "hrrr_grid": squares_doc.get("hrrr_grid"),
        "hrrr_cycle": hrrr_doc["cycle"] if hrrr_doc is not None else None,
    }
    return index, documents


def entry(path: Path, count: int, generated_at: str) -> dict:
    return {"path": to_manifest_path(path), "sha256": sha256_file(path), "count": count, "generated_at": generated_at}


def main() -> dict:
    squares_doc = json.loads(SQUARES_PATH.read_text())
    cycle_doc = json.loads(CYCLE_PATH.read_text())
    hrrr_doc = json.loads(HRRR_CYCLE_PATH.read_text()) if HRRR_CYCLE_PATH.exists() else None
    if hrrr_doc is None:
        print("::warning title=No HRRR this run::publishing NBM alone; every cell's hrrr is null (see fetch_hrrr.py's step)")
    index, documents = bake(squares_doc, cycle_doc, WEATHER_RAW, datetime.now(UTC), hrrr_doc)

    if CELL_DIR.exists():
        shutil.rmtree(CELL_DIR)
    CELL_DIR.mkdir(parents=True)
    artifacts = {}
    for cell, document in sorted(documents.items()):
        path = CELL_DIR / f"{cell}.json"
        write_text_atomically(path, json.dumps(document, separators=(",", ":")) + "\n")
        artifacts[f"{PAYLOAD}/{cell}"] = entry(path, len(document["squares"]), document["generated_at"])
    write_text_atomically(INDEX_PATH, json.dumps(index, separators=(",", ":")) + "\n")
    artifacts[INDEX_PAYLOAD] = entry(INDEX_PATH, len(documents), index["generated_at"])

    manifest = {"artifacts": artifacts}
    write_text_atomically(MANIFEST_PATH, json.dumps(manifest, indent=2) + "\n")
    total = sum(p.stat().st_size for p in CELL_DIR.glob("*.json"))
    print(
        f"Baked {cycle_doc['version']} {cycle_doc['cycle']}"
        f"{' and HRRR ' + hrrr_doc['cycle'] if hrrr_doc else ''} into {len(documents)} cells "
        f"({sum(len(d['squares']) for d in documents.values()):,} squares, {total / 1e6:.1f} MB before compression)"
    )
    return manifest


if __name__ == "__main__":
    main()
