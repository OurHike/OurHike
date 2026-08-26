"""Build the offline vector basemap - the "build once" half of the
build-once-extract-many design in BASEMAP.md (issues #184/#185).

Produces an OpenMapTiles-schema PMTiles archive covering everything within a
padded clip shape around the trail corridor, by driving two external tools:

  osmium      clips each Geofabrik state extract to the shape and merges the
              results - this pre-clip is what shrinks the Planetiler job from
              "needs a big machine" to "fits a free CI runner", because
              Planetiler's RAM and temp-disk needs scale with its input PBF
              and the corridor ribbon is a fraction of the states it crosses
  planetiler  builds the tile pyramid; its default profile emits the same
              OpenMapTiles schema OpenFreeMap serves, which is the whole
              point - client/src/map/liveTopo.ts renders the output unchanged

The shape is a PARAMETER, not an assumption. Today's one caller builds around
the AT corridor, but the design this serves cuts per-trail packages from one
shared build (extract_package.py), so nothing here may bake in "the AT" - the
same script builds around any centerline, any state list, or (on a machine
sized for it) a whole region with no clip at all (--no-clip). See BASEMAP.md
for where the bigger builds run and what they cost.

External tools, deliberately not Python dependencies: osmium-tool comes from
the OS package manager and the Planetiler jar from its GitHub releases -
both pinned/installed by .github/workflows/build-basemap.yml, documented in
BASEMAP.md for anyone running this on their own machine. This script only
*constructs* their command lines (pure, tested) and runs them; everything
that needs correctness guarantees - the clip geometry, the .poly format, the
size accounting - is in-repo Python.

Fetching is skip-if-present rather than conditional-request change-aware:
Geofabrik republishes state extracts daily, so "has it changed" is always
"yes" and the fetch_all.py-style upstream check buys nothing. A build wants
whatever is current; --refetch forces that, and CI runners start empty anyway.
"""

import argparse
import json
import subprocess
from pathlib import Path

import duckdb
from pmtiles.reader import all_tiles
from shapely.geometry import shape

from lib.corridor import build_corridor
from lib.http_retry import download_with_retry
from lib.poly import clip_shape, to_poly

ROOT = Path(__file__).parent
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
OSM_RAW_DIR = ROOT / "data" / "raw" / "osm"
OUT_DIR = ROOT / "data" / "processed"
OUT_PATH = OUT_DIR / "basemap.pmtiles"
CLIP_POLY_PATH = OSM_RAW_DIR / "clip.poly"
REGION_PATH = OUT_DIR / "basemap_region.geojson"

GEOFABRIK_BASE = "https://download.geofabrik.de/north-america/us"

# The fourteen states the AT corridor crosses - the default for --states, not
# a limit. Individual state extracts rather than us-northeast + us-south
# because the two region files together carry ~5.5 GB where these total
# ~3-4 GB, and every byte fetched here is also temp-disk the runner must hold.
AT_STATES = [
    "georgia",
    "north-carolina",
    "tennessee",
    "virginia",
    "west-virginia",
    "maryland",
    "pennsylvania",
    "new-jersey",
    "new-york",
    "connecticut",
    "massachusetts",
    "vermont",
    "new-hampshire",
    "maine",
]

# z14 is the OpenMapTiles convention and what OpenFreeMap serves; MapLibre
# overzooms it for deeper views, exactly as the live sheet does today.
BASEMAP_MAX_ZOOM = 14


def state_urls(states: list[str]) -> list[tuple[str, str]]:
    """(state, download URL) for each Geofabrik state extract."""
    return [(state, f"{GEOFABRIK_BASE}/{state}-latest.osm.pbf") for state in states]


def fetch_states(states: list[str], dest_dir: Path, refetch: bool = False) -> list[Path]:
    """Download each state's PBF into dest_dir, skipping files already present
    unless refetch. Returns the local paths in the order given."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for state, url in state_urls(states):
        dest = dest_dir / f"{state}-latest.osm.pbf"
        paths.append(dest)
        if dest.exists() and not refetch:
            print(f"  {state}: already present ({dest.stat().st_size / 1e6:.0f} MB), skipping")
            continue
        print(f"  {state}: fetching {url}")
        # Retried whole rather than resumed, and streamed to a .part that only
        # a completed transfer renames into place - download_with_retry's
        # docstring holds the reasoning, and #1063 the failure that demanded
        # it: one mid-body connection reset from Geofabrik ended an entire
        # production publish, twice in one evening. The granularity is right
        # because this loop already persists per state - a retry re-pulls one
        # extract, never the fourteen.
        download_with_retry(url, dest, timeout=600, label=state)
        print(f"  {state}: {dest.stat().st_size / 1e6:.0f} MB")
    return paths


def osmium_extract_cmd(src_pbf: Path, poly_path: Path, out_pbf: Path) -> list[str]:
    """osmium extract: clip one PBF to the .poly shape."""
    return ["osmium", "extract", "--polygon", str(poly_path), "--overwrite", "-o", str(out_pbf), str(src_pbf)]


def osmium_merge_cmd(inputs: list[Path], out_pbf: Path) -> list[str]:
    """osmium merge: combine the clipped per-state PBFs into one build input."""
    return ["osmium", "merge", "--overwrite", "-o", str(out_pbf), *[str(p) for p in inputs]]


def planetiler_cmd(
    jar: Path,
    osm_pbf: Path,
    out_path: Path,
    max_zoom: int,
    poly_path: Path | None,
    tmp_dir: Path,
    layer_stats: bool = False,
    http_timeout_seconds: int | None = None,
) -> list[str]:
    """The Planetiler invocation. --download fetches the profile's non-OSM
    sources (Natural Earth, water polygons) on first run; --polygon bounds the
    output tiles to the clip shape (omitted under --no-clip, where the input
    PBF's own extent is the bound).

    layer_stats asks for the per-(tile, layer) TSV that compare_shards.py
    reads. Off by default and opt-in rather than always on: Planetiler names
    the file whether or not it writes one - the `layer_stats` argument it
    logs is a path, not a promise - and a build that pays for statistics
    nobody reads is a build paying for nothing. The spike turns it on.

    http_timeout_seconds raises Planetiler's own 30s default. The profile
    pulls ~1.4 GB from three third parties before it builds anything, and
    `Error getting size of water-polygons-split-3857.zip ... TimeoutException`
    is that 30s expiring on a slow host - a failure that says nothing about
    the data and stops the build regardless. None leaves Planetiler's
    default alone."""
    return [
        "java",
        "-jar",
        str(jar),
        f"--osm-path={osm_pbf}",
        f"--output={out_path}",
        f"--maxzoom={max_zoom}",
        f"--tmpdir={tmp_dir}",
        *([] if poly_path is None else [f"--polygon={poly_path}"]),
        *(["--output-layerstats"] if layer_stats else []),
        *([] if http_timeout_seconds is None else [f"--http-timeout={http_timeout_seconds}s"]),
        "--download",
        "--force",
    ]


def load_corridor_4326():
    """The corridor as a shapely geometry in EPSG:4326, built fresh from the
    centerline exactly as the raster pipeline does (and never from the stale
    spike output - see lib/corridor.py)."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    build_corridor(con, CENTERLINE_PATH)
    geojson = con.execute("SELECT ST_AsGeoJSON(geom) FROM corridor").fetchone()[0]
    return shape(json.loads(geojson))


def write_shapes(corridor) -> None:
    """The two derived shapes, and why they differ: the padded .poly bounds
    what the BUILD considers (lib/poly.py's superset guarantee), while the
    exact corridor GeoJSON is what extract_package.py cuts the shipped
    package against. Conflating them would either ship padding or clip the
    build to a boundary features should cross whole."""
    OSM_RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CLIP_POLY_PATH.write_text(to_poly(clip_shape(corridor), name="basemap-clip"))
    REGION_PATH.write_text(json.dumps({"type": "Feature", "properties": {}, "geometry": corridor.__geo_interface__}))
    print(f"Clip shape -> {CLIP_POLY_PATH}")
    print(f"Package region -> {REGION_PATH}")


def report_archive(path: Path) -> dict[int, tuple[int, int]]:
    """Per-zoom (tile count, addressed bytes) for a PMTiles archive, printed
    the way pipeline/README.md tabulates the raster tiers. Addressed bytes
    overcount the file where tiles deduplicate; the physical size printed
    alongside is the number a download actually costs."""
    per_zoom: dict[int, list[int]] = {}
    with open(path, "rb") as f:

        def get_bytes(offset, length):
            f.seek(offset)
            return f.read(length)

        for (z, _x, _y), data in all_tiles(get_bytes):
            counts = per_zoom.setdefault(z, [0, 0])
            counts[0] += 1
            counts[1] += len(data)

    print(f"\n{path.name}: {path.stat().st_size / 1e6:.1f} MB on disk")
    print(f"{'zoom':>4}  {'tiles':>8}  {'MB':>8}")
    for z in sorted(per_zoom):
        tiles, size = per_zoom[z]
        print(f"{z:>4}  {tiles:>8}  {size / 1e6:>8.1f}")
    return {z: (t, b) for z, (t, b) in per_zoom.items()}


def main(args: argparse.Namespace):
    if args.no_clip and args.states == AT_STATES:
        raise SystemExit("--no-clip over the full default state list needs a machine sized for it - pass --states explicitly.")

    print("Building corridor from centerline...")
    corridor = load_corridor_4326()
    write_shapes(corridor)

    print(f"Fetching {len(args.states)} state extracts...")
    state_pbfs = fetch_states(args.states, OSM_RAW_DIR, refetch=args.refetch)

    merged = OSM_RAW_DIR / "basemap-input.osm.pbf"
    if args.no_clip:
        clipped = state_pbfs
    else:
        print("Clipping each state to the corridor shape...")
        clipped = []
        for pbf in state_pbfs:
            out = pbf.with_name(f"clipped-{pbf.name}")
            subprocess.run(osmium_extract_cmd(pbf, CLIP_POLY_PATH, out), check=True)
            clipped.append(out)
            print(f"  {pbf.name}: {pbf.stat().st_size / 1e6:.0f} MB -> {out.stat().st_size / 1e6:.0f} MB")
    print("Merging...")
    subprocess.run(osmium_merge_cmd(clipped, merged), check=True)
    print(f"Build input: {merged.stat().st_size / 1e6:.0f} MB")

    if args.planetiler_jar is None:
        print("\nNo --planetiler-jar given - stopping after clip+merge (see BASEMAP.md for the jar).")
        return

    print("Running Planetiler...")
    tmp_dir = OSM_RAW_DIR / "planetiler-tmp"
    cmd = planetiler_cmd(args.planetiler_jar, merged, args.out, args.max_zoom, None if args.no_clip else CLIP_POLY_PATH, tmp_dir)
    print(f"  {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    report_archive(args.out)


if __name__ == "__main__":
    # Parsed outside main() for the same reason fetch_elevation.py does it:
    # tests call main() directly with module state patched, and argparse with
    # no argv would read pytest's own command line.
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--states", nargs="+", default=AT_STATES, help="Geofabrik state names (default: the 14 AT states)")
    parser.add_argument("--planetiler-jar", type=Path, default=None, help="Path to planetiler.jar; omit to stop after clip+merge")
    parser.add_argument("--max-zoom", type=int, default=BASEMAP_MAX_ZOOM, help=f"Tile pyramid depth (default {BASEMAP_MAX_ZOOM})")
    parser.add_argument("--out", type=Path, default=OUT_PATH, help=f"Output .pmtiles path (default {OUT_PATH})")
    parser.add_argument("--refetch", action="store_true", help="Re-download state extracts even if already present")
    parser.add_argument("--no-clip", action="store_true", help="Skip the corridor clip and build the states whole (big machine)")
    main(parser.parse_args())
