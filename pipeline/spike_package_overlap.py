"""How many bytes would a phone holding two trail packages store twice? (#193)

Build-once-extract-many cuts every trail's package from one shared build, and
overlapping regions therefore duplicate tiles on a phone that downloads both.
The decision #193 exists to make - accept the duplication, reshape packages,
or content-address the store - needs the waste measured, not guessed. This
measures it against the real published archives: the AT corridor package as
package A, and a second package modelled by the exact region shape a
statewide build would be cut with (Geofabrik's .poly for the state, parsed by
lib/poly.from_poly - the same boundary export_basemap.py's state extracts are
already clipped to, so the second region is the system's own shape rather
than a cartographic stand-in).

What counts as shared, per zoom:

  context     through the package's context zoom (extract_package.py ships
              every source tile through z9), BOTH packages carry the whole
              build footprint, so every archive tile at those zooms is
              duplicated by construction.
  region      above it, a tile is shared iff it intersects both regions -
              the same tiles_intersecting() walk both extracts would run.

Bytes are the archive's own directory entries, so the duplicated megabytes
are exact for package A's actual bytes - not tile counts times an average.

The DEM archive has no context mechanism (export_dem.py walks the region at
every zoom), so its context zoom is "none".
"""

import argparse
from collections import defaultdict
from pathlib import Path

import requests
from pmtiles.reader import deserialize_directory
from pmtiles.tile import deserialize_header, tileid_to_zxy

from export_basemap import load_corridor_4326
from extract_package import DEFAULT_CONTEXT_ZOOM, load_region, tiles_intersecting, to_mercator
from lib.poly import from_poly

ROOT = Path(__file__).parent
PROCESSED_DIR = ROOT / "data" / "processed"

NY_POLY_URL = "https://download.geofabrik.de/north-america/us/new-york.poly"


def load_poly(source: str):
    """A region from an Osmosis .poly, by URL or local path."""
    if source.startswith("http://") or source.startswith("https://"):
        resp = requests.get(source, timeout=120)
        resp.raise_for_status()
        return from_poly(resp.text)
    return from_poly(Path(source).read_text())


def archive_entries(path: Path):
    """Every (z, x, y, stored_length) in the archive, from its directories
    alone - tile data is never read, so this is cheap even at 600 MB."""
    with open(path, "rb") as f:

        def get_bytes(offset, length):
            f.seek(offset)
            return f.read(length)

        header = deserialize_header(get_bytes(0, 127))

        def walk(offset, length):
            for entry in deserialize_directory(get_bytes(offset, length)):
                if entry.run_length == 0:
                    yield from walk(header["leaf_directory_offset"] + entry.offset, entry.length)
                else:
                    for i in range(entry.run_length):
                        z, x, y = tileid_to_zxy(entry.tile_id + i)
                        yield z, x, y, entry.length

        yield from walk(header["root_offset"], header["root_length"])


def shared_tiles(
    entries,
    region_b_merc,
    max_zoom: int,
    context_zoom: int | None,
) -> dict[int, dict[str, int]]:
    """Per-zoom {tiles, bytes, shared_tiles, shared_bytes} for one archive
    against a second region.

    `entries` is archive_entries() output (or anything shaped like it);
    `context_zoom` is the zoom through which the archive carries the whole
    build footprint - shared by construction - or None for an archive that
    is region-only at every zoom (the DEM)."""
    hits = tiles_intersecting(region_b_merc, 0, max_zoom)
    in_b = {z: set(tiles) for z, tiles in hits.items()}
    context = -1 if context_zoom is None else context_zoom

    table: dict[int, dict[str, int]] = defaultdict(lambda: {"tiles": 0, "bytes": 0, "shared_tiles": 0, "shared_bytes": 0})
    for z, x, y, length in entries:
        row = table[z]
        row["tiles"] += 1
        row["bytes"] += length
        if z <= context or (x, y) in in_b.get(z, ()):
            row["shared_tiles"] += 1
            row["shared_bytes"] += length
    return dict(table)


def report(name: str, table: dict[int, dict[str, int]]) -> str:
    lines = [f"{name}", "zoom     tiles        MB    shared  shared MB"]
    total = {"tiles": 0, "bytes": 0, "shared_tiles": 0, "shared_bytes": 0}
    for z in sorted(table):
        row = table[z]
        for key in total:
            total[key] += row[key]
        lines.append(
            f"{z:4d} {row['tiles']:9d} {row['bytes'] / 1e6:9.1f} {row['shared_tiles']:9d} {row['shared_bytes'] / 1e6:10.1f}"
        )
    share = total["shared_bytes"] / total["bytes"] * 100 if total["bytes"] else 0.0
    lines.append(
        f"TOTAL {total['tiles']:8d} {total['bytes'] / 1e6:9.1f} {total['shared_tiles']:9d} "
        f"{total['shared_bytes'] / 1e6:10.1f}  ({share:.1f}% of the archive's bytes)"
    )
    return "\n".join(lines)


def fetch_archive(base_url: str, key: str, dest: Path) -> Path:
    """Download a published archive if it is not already beside us - the
    spike runs on hosted runners where nothing persists between runs."""
    if dest.exists():
        print(f"{dest} already present, {dest.stat().st_size / 1e6:.1f} MB")
        return dest
    url = f"{base_url.rstrip('/')}/{key}"
    print(f"Fetching {url}...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(1 << 20):
                f.write(chunk)
    print(f"  {dest.stat().st_size / 1e6:.1f} MB")
    return dest


def main(args: argparse.Namespace) -> None:
    if args.region is None:
        print("Building corridor from centerline...")
        region_a = load_corridor_4326()
    else:
        region_a = load_region(args.region)
    region_b = load_poly(args.poly)
    region_b_merc = to_mercator(region_b)

    # Sanity worth printing: the two regions must actually overlap, or every
    # number below is a zero that looks like a finding.
    overlap = region_a.intersection(region_b)
    print(f"Regions overlap over ~{overlap.area:.2f} sq deg (A is {region_a.area:.2f}, B is {region_b.area:.2f})\n")

    reports = []
    for label, path, max_zoom, context in (
        ("at_basemap_package.pmtiles vs a statewide package (context through z9)", args.basemap, 14, DEFAULT_CONTEXT_ZOOM),
        ("dem.pmtiles vs a statewide DEM package (no context zooms)", args.dem, 13, None),
    ):
        if path is None or not path.exists():
            print(f"{label}: archive not present, skipped")
            continue
        table = shared_tiles(archive_entries(path), region_b_merc, max_zoom, context)
        reports.append(report(label, table))

    print("\n\n".join(reports))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", type=Path, default=None, help="Package A's region GeoJSON (default: build the AT corridor)")
    parser.add_argument("--poly", default=NY_POLY_URL, help=f"Second region's Osmosis .poly, URL or path (default {NY_POLY_URL})")
    parser.add_argument("--basemap", type=Path, default=PROCESSED_DIR / "at_basemap_package.pmtiles")
    parser.add_argument("--dem", type=Path, default=PROCESSED_DIR / "dem.pmtiles")
    parser.add_argument("--fetch-from", default=None, help="Public bucket base URL to download missing archives from")
    args = parser.parse_args()
    if args.fetch_from:
        fetch_archive(args.fetch_from, "at_basemap_package.pmtiles", args.basemap)
        fetch_archive(args.fetch_from, "dem.pmtiles", args.dem)
    main(args)
