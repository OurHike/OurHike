"""Which NBM forecast squares each trail cell's weather file carries (#1056).

The maintainer's call of 2026-09-24, taken against a drawing of the real
squares around Damascus, VA: **the squares under a trail or a waypoint, and no
others** ("A" of three). Measured on release 2026-09-23 against NOAA's grid,
that is 73,973 squares across the 442 trail cells on the CONUS grid - 167 per
cell on average, against 1,582 in a whole cell - which is what keeps a
five-cell stretch to a few hundred KB a refresh rather than over a megabyte.
The cost of the choice, written down so it is not rediscovered: a spot more
than a square from any trail or waypoint has no forecast, and the card says
so rather than borrowing one (features/WEATHER.md §7).

This is the static half of the weather job. Trails and waypoints change with
a data release, not with the forecast, so this runs against the environment's
current release and caches its answer under that release's id; the hourly
half (`fetch_weather.py`, `export_weather.py`) reads the answer and nothing
else about trails.

WATER SQUARES BORROW A LAND NEIGHBOUR (WEATHER.md §6). A trail point by a
river can sit in a square the model treats as water - Bear Mountain's
published coordinate is in square (712, 2007), whose terrain height in NOAA's
URMA analysis is 0 m: the Hudson. A water square's temperature is the river's,
not the summit path's. So a square whose URMA terrain is at or below
`WATER_MAX_M` reads the nearest square within `BORROW_RINGS` whose terrain is
above it, and the file says which squares borrowed.

@unvalidated, and narrower than it sounds. Terrain at or below 0 m finds
sea-level water - the ocean, the tidal Hudson - and nothing else: a lake
surface sits at its own height (Lake Champlain ~30 m) and passes as land, and
NBM's own sea-surface field marks the ocean only (measured 2026-09-24: the
Hudson, Lake Champlain and Lake George all read as land in it). A land mask
proper arrives with HRRR's `LAND` field in step 1's HRRR slice; what would
settle whether lake squares matter is comparing a lake-shore trail square's
forecast with its landward neighbour's over a season.

EACH SQUARE'S NWS ZONES (the warnings slice, 2026-09-26). Most NWS alerts name
the zones they cover rather than drawing a shape - 419 of 486 active at
2026-09-25 20:54 UTC - so placing them needs NWS's zone outlines, which change
a few times a year rather than with the forecast. So this script also
lists, for every trail square, the public forecast zones, fire weather zones
and counties whose outline overlaps any part of it (`lib/nbm_grid.overlapping`,
and WEATHER.md §6 for why any part). `export_weather_alerts.py` reads that to
place an alert; `export_weather.py` hands each square's list to the phone,
which asks NWS for exactly those zones when it has signal (the maintainer's
choice of 2026-09-26, WEATHER.md §5). Measured 2026-09-26 on UA release
2026-09-25, in a sandbox: 3.5 s to download the three files (68 MB), 1.9 s to
read them and 4.1 s to place all 72,720 squares, where testing the 9.6 million
trail points one by one took 11 minutes. 17% of squares straddle two or more
forecast zones. 3 lie in none: two in the sea off Long Island's south shore,
one at the Isles of Shoals off New Hampshire, where no zone outline reaches.

    OURHIKE_DATA_ENV=ua DATA_BASE_URL=https://data.ourhike.org python build_weather_squares.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
import rasterio
import requests
import shapely

from cut_cells import cell_name
from lib import data_env, nbm_grid
from lib.atomic_write import write_text_atomically
from lib.http_retry import download_with_retry, request_with_retry

ROOT = Path(__file__).resolve().parent
WEATHER_RAW = ROOT / "data" / "raw" / "weather"
RELEASE_DIR = WEATHER_RAW / "release"
SQUARES_PATH = WEATHER_RAW / "squares.json"
TERRAIN_PATH = WEATHER_RAW / "urma_terrain.grb2"
ZONES_DIR = WEATHER_RAW / "zones"

USER_AGENT = "OurHike (github.com/OurHike/OurHike)"
URMA_BUCKET = "https://noaa-urma-pds.s3.amazonaws.com"

# Bumped when the answer this script writes changes meaning, so a cached
# squares.json from an older rule is rebuilt rather than reused because its
# release id still matches. 2: each square's NWS zones (the warnings slice).
SCHEMA = 2

# Points are laid along each line at most this far apart in either axis
# before being dropped into squares. Derived, not picked: a square is 2.54 km,
# and 0.004 degrees is at most ~0.45 km of latitude (less of longitude), so a
# line crossing a square is sampled inside it unless it clips a corner for
# less than that - a square whose neighbours on the line are all included.
STEP_DEG = 0.004

# At or below this URMA terrain height a square is treated as water. See the
# module docstring for what this does and does not catch.
WATER_MAX_M = 0.0

# How far a water square looks for land: two squares, ~5 km. A trail point
# is on land by definition, so its square's land neighbour is almost always
# one square away; a square with no land within two is open water and keeps
# its own forecast, listed as such.
BORROW_RINGS = 2

# NWS's zone outlines, pinned to the files current on 2026-09-26 and checked
# against the MD5 NWS publishes beside each (weather.gov/gis/PublicZones,
# /FireZones, /Counties - all three matched). Pinned rather than discovered
# because the page is HTML meant for people, and a scrape that misread it
# would place every warning in last year's zones without a sound. The cost is
# that NWS replaces these files a few times a year (the 16 April 2026 set
# followed 18 March 2025's): `export_weather_alerts.py` reports any zone an
# alert names that is not in them, and a newer file is a one-line change here.
# Each entry: the file, its MD5, and how an alert's zone id is spelled from a
# row - the id NWS's `affectedZones` URLs end in (/zones/<kind>/<id>).
ZONE_FILES = {
    "forecast": (
        "https://www.weather.gov/source/gis/Shapefiles/WSOM/z_16ap26.zip",
        "004dc6501dc3d50e7b36652cb9d02bd3",
        "STATE || 'Z' || ZONE",
    ),
    "fire": (
        "https://www.weather.gov/source/gis/Shapefiles/WSOM/fz16ap26.zip",
        "17862cbdb414d7b0807ac1765b2af3d0",
        "STATE || 'Z' || ZONE",
    ),
    # A county's id is its state, "C", and the last three digits of its FIPS
    # code: Montgomery County, MD is FIPS 24031 and zone MDC031.
    "county": (
        "https://www.weather.gov/source/gis/Shapefiles/County/c_16ap26.zip",
        "734d75df3791bdc0cbb29fd6ed75a387",
        "STATE || 'C' || substr(FIPS, 3, 3)",
    ),
}

# The runtime pin against a mirrored or shifted terrain decode (WEATHER.md §6,
# the first trap): Mount Washington's square must come back as a mountain.
# URMA's value there measured 1,702 m on 2026-09-24; the summit is 1,917 m.
# A decode that mirrored rows or read another grid puts somewhere else's
# height here, and nowhere else on this grid is this high near this square.
MOUNT_WASHINGTON = (-71.3033, 44.2706)
MOUNT_WASHINGTON_TERRAIN_M = (1500.0, 1950.0)

POI_KEY = re.compile(r"^(poi_[a-z_]+|nearby_poi)\.geojson$")
LINE_KEYS = ("trails.geojson", "nearby_trails.geojson")


# --------------------------------------------------------------------------
# Pure pieces - what the tests pin.


def densify(line: np.ndarray, step_deg: float = STEP_DEG) -> np.ndarray:
    """A line's vertices plus points laid between them no more than
    `step_deg` apart in either axis. `line` is (n, 2) lon/lat."""
    line = np.asarray(line, dtype=float)[:, :2]
    if len(line) < 2:
        return line
    delta = np.diff(line, axis=0)
    pieces = np.maximum(1, np.ceil(np.abs(delta).max(axis=1) / step_deg)).astype(np.int64)
    starts = np.repeat(line[:-1], pieces, axis=0)
    steps = np.repeat(delta / pieces[:, None], pieces, axis=0)
    offsets = np.concatenate([np.arange(k) for k in pieces])[:, None]
    return np.vstack([starts + steps * offsets, line[-1:]])


def geometry_lines(geometry: dict | None) -> list[list]:
    if not geometry:
        return []
    if geometry["type"] == "LineString":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiLineString":
        return geometry["coordinates"]
    return []


def cells_of(lons: np.ndarray, lats: np.ndarray) -> list[str]:
    """Each point's 1-degree cell, named the way the coverage cells are."""
    return [cell_name(math.floor(lon), math.floor(lat)) for lon, lat in zip(lons, lats, strict=True)]


def squares_by_cell(lons: np.ndarray, lats: np.ndarray) -> tuple[dict[str, list[list[int]]], list[str]]:
    """({cell: sorted [row, col] squares}, sorted cells off the CONUS grid).

    A square straddling two cells is listed in each cell a trail point in it
    falls in, so every cell's file is complete on its own."""
    rows, cols = nbm_grid.squares(lons, lats)
    names = cells_of(lons, lats)
    found: dict[str, set[tuple[int, int]]] = {}
    outside: set[str] = set()
    for name, row, col in zip(names, rows.tolist(), cols.tolist(), strict=True):
        if row < 0:
            outside.add(name)
            continue
        found.setdefault(name, set()).add((row, col))
    return {name: [list(sq) for sq in sorted(found[name])] for name in sorted(found)}, sorted(outside - set(found))


def borrow_land(
    squares: set[tuple[int, int]], terrain: np.ndarray, water_max_m: float = WATER_MAX_M, rings: int = BORROW_RINGS
) -> tuple[dict[tuple[int, int], tuple[int, int]], list[tuple[int, int]]]:
    """({water square: land square it reads from}, water squares with no land
    near enough, which keep their own forecast).

    Nearest by grid distance; a tie goes to the smaller (row, col), so the
    answer does not depend on set order."""
    height, width = terrain.shape
    borrowed: dict[tuple[int, int], tuple[int, int]] = {}
    kept: list[tuple[int, int]] = []
    for row, col in sorted(squares):
        if terrain[row, col] > water_max_m:
            continue
        best = None
        for dr in range(-rings, rings + 1):
            for dc in range(-rings, rings + 1):
                r, c = row + dr, col + dc
                if (dr, dc) == (0, 0) or not (0 <= r < height and 0 <= c < width):
                    continue
                if terrain[r, c] <= water_max_m:
                    continue
                key = (dr * dr + dc * dc, r, c)
                if best is None or key < best:
                    best = key
        if best is None:
            kept.append((row, col))
        else:
            borrowed[(row, col)] = (best[1], best[2])
    return borrowed, kept


def check_terrain(terrain: np.ndarray) -> None:
    """Refuse a terrain grid whose Mount Washington square is not a mountain."""
    rows, cols = nbm_grid.squares([MOUNT_WASHINGTON[0]], [MOUNT_WASHINGTON[1]])
    value = float(terrain[int(rows[0]), int(cols[0])])
    low, high = MOUNT_WASHINGTON_TERRAIN_M
    if not low <= value <= high:
        raise RuntimeError(
            f"URMA terrain at Mount Washington's square reads {value:.0f} m, outside {low:.0f}-{high:.0f} m. "
            "The grid decoded mirrored, shifted or from the wrong file; refusing to pick land squares from it."
        )


def zones_by_square(square_list: list[list[int]], layers: dict[str, tuple[list[str], list]]) -> dict[str, list[list[int]]]:
    """{"<kind>/<id>": sorted [row, col] squares it overlaps}, for every zone
    in `layers` ({kind: (ids, lon/lat shapely geometries)}) that overlaps at
    least one square. A zone NWS draws as several rows - a county split
    between two forecast offices is two - is one entry."""
    found: dict[str, set[tuple[int, int]]] = {}
    for kind, (ids, geometries) in layers.items():
        for zone_id, hits in zip(ids, nbm_grid.overlapping(geometries, square_list), strict=True):
            if hits:
                found.setdefault(f"{kind}/{zone_id}", set()).update(tuple(square_list[i]) for i in hits)
    return {key: [list(sq) for sq in sorted(found[key])] for key in sorted(found)}


# --------------------------------------------------------------------------
# The release, and the terrain. Network.


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def fetch_release(base: str, latest: dict) -> tuple[str, list[Path]]:
    """(release id, local paths of the trail and waypoint files in it), for
    the release `latest` (the environment's latest.json) points at."""
    release = latest["release"]
    keys = [k for k in latest["artifacts"] if k in LINE_KEYS or POI_KEY.match(k)]
    if "trails.geojson" not in keys:
        raise RuntimeError(f"release {release} carries no trails.geojson; nothing to put weather under")
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for key in sorted(keys):
        dest = RELEASE_DIR / key
        download_with_retry(f"{base}/releases/{release}/{key}", dest, label=key, headers={"User-Agent": USER_AGENT})
        paths.append(dest)
    return release, paths


def newest_urma_file(session: requests.Session, today: datetime | None = None) -> str:
    """The key of a recent URMA 2.5 km analysis. Terrain does not change, so
    any recent one serves; today's or yesterday's is simply what exists."""
    today = today or datetime.now(UTC)
    for back in range(3):
        day = (today - timedelta(days=back)).strftime("%Y%m%d")
        listing = request_with_retry(
            f"{URMA_BUCKET}/", session=session, params={"list-type": "2", "prefix": f"urma2p5.{day}/"}, label="URMA listing"
        ).text
        keys = [el.text for el in ET.fromstring(listing).iter() if el.tag.endswith("Key")]
        grids = sorted(k for k in keys if k.endswith("2dvaranl_ndfd.grb2_wexp"))
        if grids:
            return grids[-1]
    raise RuntimeError("no URMA 2dvaranl file in the last three days")


def fetch_terrain(session: requests.Session) -> np.ndarray:
    """URMA's surface height, on NBM's grid, read with GDAL's GRIB driver."""
    if not TERRAIN_PATH.exists():
        key = newest_urma_file(session)
        index = request_with_retry(f"{URMA_BUCKET}/{key}.idx", session=session, label="URMA idx").text.splitlines()
        first, second = index[0].split(":"), index[1].split(":")
        if first[3] != "HGT" or first[4] != "surface":
            raise RuntimeError(f"URMA's first message is {first[3]}:{first[4]}, not HGT:surface - the file layout moved")
        start, end = int(first[1]), int(second[1]) - 1
        body = request_with_retry(
            f"{URMA_BUCKET}/{key}", session=session, headers={"Range": f"bytes={start}-{end}"}, label="URMA terrain"
        ).content
        TERRAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TERRAIN_PATH.write_bytes(body)
    with rasterio.open(TERRAIN_PATH) as ds:
        if not nbm_grid.matches(ds.transform, ds.crs, ds.width, ds.height):
            raise RuntimeError("URMA's terrain is not on NBM's grid; the pinned grid in lib/nbm_grid.py no longer holds")
        terrain = ds.read(1).astype(np.float64)
    check_terrain(terrain)
    return terrain


def fetch_zone_file(kind: str) -> Path:
    """One of NWS's zone shapefiles, downloaded once and refused unless its
    MD5 is the one pinned in `ZONE_FILES`."""
    url, md5, _ = ZONE_FILES[kind]
    dest = ZONES_DIR / url.rsplit("/", 1)[-1]
    if not dest.exists() or hashlib.md5(dest.read_bytes()).hexdigest() != md5:
        ZONES_DIR.mkdir(parents=True, exist_ok=True)
        download_with_retry(url, dest, timeout=120, headers={"User-Agent": USER_AGENT}, label=dest.name)
    actual = hashlib.md5(dest.read_bytes()).hexdigest()
    if actual != md5:
        dest.unlink()
        raise RuntimeError(
            f"{dest.name} has MD5 {actual}, not the pinned {md5}: NWS replaced the file under the same name, "
            "or the download was cut short. Check weather.gov/gis for the current file and its sum."
        )
    return dest


def read_zone_file(path: Path, id_sql: str) -> tuple[list[str], list]:
    """(zone ids, lon/lat geometries), one per row of the shapefile inside
    the zip. The files are NAD83, which this treats as the same lon/lat as
    the trail data's - the two differ by a metre or two in CONUS, against a
    2.5 km square."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    shp = path.name.removesuffix(".zip") + ".shp"
    rows = con.execute(f"SELECT {id_sql}, ST_AsWKB(geom) FROM ST_Read('/vsizip/{path}/{shp}')").fetchall()
    con.close()
    return [r[0] for r in rows], list(shapely.from_wkb([bytes(r[1]) for r in rows]))


# --------------------------------------------------------------------------


def trail_points(paths: list[Path]) -> tuple[np.ndarray, np.ndarray]:
    """Every densified trail point and every waypoint, as (lons, lats)."""
    chunks = []
    for path in paths:
        for feature in json.loads(path.read_text())["features"]:
            geometry = feature.get("geometry")
            if geometry and geometry["type"] == "Point":
                chunks.append(np.asarray([geometry["coordinates"][:2]], dtype=float))
                continue
            for line in geometry_lines(geometry):
                if len(line) >= 2:
                    chunks.append(densify(np.asarray([c[:2] for c in line], dtype=float)))
    points = np.vstack(chunks)
    return points[:, 0], points[:, 1]


def cached_release() -> str | None:
    try:
        cached = json.loads(SQUARES_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return cached.get("release") if cached.get("schema") == SCHEMA else None


def main(argv: list[str] | None = None) -> dict | None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", help="data base URL; defaults to $DATA_BASE_URL")
    parser.add_argument("--env", help="data environment to read; defaults to $OURHIKE_DATA_ENV")
    args = parser.parse_args(argv)
    env = data_env.resolve(args.env)
    base = data_env.resolve_base(args.base, env)
    if not base:
        raise SystemExit("No data base URL: pass --base or set DATA_BASE_URL.")

    session = _session()
    latest = request_with_retry(f"{base}/latest.json", session=session, label="latest.json").json()
    if cached_release() == latest["release"]:
        print(f"Squares already built for {env} release {latest['release']}; nothing to do.")
        return None

    release, paths = fetch_release(base, latest)
    lons, lats = trail_points(paths)
    cells, outside = squares_by_cell(lons, lats)
    all_squares = {tuple(sq) for squares in cells.values() for sq in squares}
    borrowed, kept = borrow_land(all_squares, fetch_terrain(session))
    layers = {kind: read_zone_file(fetch_zone_file(kind), spec[2]) for kind, spec in ZONE_FILES.items()}
    zones = zones_by_square(sorted(list(sq) for sq in all_squares), layers)
    zoned = {tuple(sq) for squares in zones.values() for sq in squares}

    document = {
        "schema": SCHEMA,
        "environment": env,
        "release": release,
        "built_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "grid": {"proj4": nbm_grid.PROJ4, "origin": [nbm_grid.ORIGIN_X, nbm_grid.ORIGIN_Y], "square_m": nbm_grid.SQUARE_M},
        "cells": cells,
        "borrowed": sorted([list(water), list(land)] for water, land in borrowed.items()),
        "water_kept": sorted(list(sq) for sq in kept),
        "outside_grid": outside,
        "zone_files": {kind: spec[0].rsplit("/", 1)[-1] for kind, spec in ZONE_FILES.items()},
        "zones": zones,
        # Every zone id in the pinned files, trail or not, so the alerts
        # export can tell "a zone nowhere near a trail" from "a zone these
        # files have never heard of" - the second means the pin is stale.
        "known_zones": {kind: sorted(set(layers[kind][0])) for kind in ZONE_FILES},
    }
    write_text_atomically(SQUARES_PATH, json.dumps(document, separators=(",", ":")) + "\n")
    print(
        f"{env} release {release}: {len(all_squares):,} squares in {len(cells)} cells from {len(lons):,} points; "
        f"{len(borrowed)} water squares borrow land, {len(kept)} keep their own; "
        f"{len(outside)} cells off the CONUS grid ({', '.join(outside) or 'none'}); "
        f"{len(zones):,} NWS zones overlap a trail square, {len(all_squares) - len(zoned)} squares are in none."
    )
    return document


if __name__ == "__main__":
    main()
