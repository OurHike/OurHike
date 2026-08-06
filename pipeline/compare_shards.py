"""Compare a control basemap build against the same ground built as shards -
the measurement half of the sharded-build question BASEMAP.md raises for
#194.

The claim under test is that a continental build can be split across free
runners: low zooms once nationally, high zooms per sub-region, with the
shards never reconciled because they are disjoint. That is only true if a
tile built inside a shard is the tile the whole-region build would have
produced. This script answers whether it is, and when it is not, answers the
question that decides whether the design survives:

  ARE THE DIFFERENCES AT THE SEAM, OR EVERYWHERE?

Seam-local differences are a padding problem - a feature crossing the shard
boundary got cut because the shard's INPUT stopped there. More padding fixes
it, and the histogram this prints says how much. Differences spread through
a shard's interior are something else: Planetiler deciding a feature's fate
from a view of the whole input rather than the tile's neighbourhood. No
padding fixes that, and it is the thing BASEMAP.md flags as unproved.

Distinguishing the two is the entire point, and it is why this reports a
distance histogram rather than a pass/fail count. A bare "1,412 tiles
differ" cannot tell those two futures apart.

## What it reads

Planetiler's own `--layer-stats` TSV, one row per (tile, layer), rather than
a vector-tile parser. Two reasons: it is Planetiler's accounting rather than
a reimplementation of it that could be wrong in the direction that hides a
difference, and it carries `layer_attr_values`, which moves when an
attribute's VALUE changes even though the feature count does not. A
re-ranked city is exactly that shape of change - same feature, different
`rank` - so a comparison on feature counts alone would call it identical.

Tile bytes from the archives themselves are hashed alongside it. Layer stats
localise a difference to a layer and a metric; the hash is what actually
decides "same tile or not", since two different tiles can encode to the same
byte count.
"""

import argparse
import gzip
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from pmtiles.reader import all_tiles
from pyproj import Transformer
from shapely.geometry import box, shape
from shapely.ops import transform
from shapely.prepared import prep

from lib.tiling import tile_bounds_merc, tile_range_for_bounds

# The layer-stats columns this reads. Planetiler writes more (hilbert index,
# attribute key/value counts); these are the ones a difference can hide in.
STAT_FIELDS = ("layer_bytes", "layer_features", "layer_geometries", "layer_attr_bytes", "layer_attr_values")

# Ring search stops here. A difference further than this from the seam is
# already "not seam-local" for the purpose of the verdict, and the exact
# distance stops carrying information worth the search cost.
MAX_SEAM_DISTANCE = 8

Tile = tuple[int, int, int]


@dataclass(frozen=True)
class Difference:
    """One (tile, layer, metric) disagreement between control and shards.

    `metric` is None for a tile present in one build and absent from the
    other, which is a different kind of finding from a tile whose contents
    drifted and is counted separately."""

    tile: Tile
    layer: str | None
    metric: str | None
    control: int | None
    sharded: int | None

    @property
    def kind(self) -> str:
        if self.metric is None:
            return "missing-from-shards" if self.sharded is None else "extra-in-shards"
        return "value"


def read_layer_stats(path: Path) -> dict[Tile, dict[str, dict[str, int]]]:
    """Planetiler's gzipped layer-stats TSV as {tile: {layer: {metric: n}}}.

    Columns are looked up by header name rather than position: Planetiler has
    added columns before, and a positional read would silently start
    comparing the wrong number rather than failing."""
    stats: dict[Tile, dict[str, dict[str, int]]] = defaultdict(dict)
    with gzip.open(path, "rt") as f:
        header = f.readline().rstrip("\n").split("\t")
        index = {name: i for i, name in enumerate(header)}
        missing = [c for c in ("z", "x", "y", "layer", *STAT_FIELDS) if c not in index]
        if missing:
            raise SystemExit(f"{path}: layer stats missing expected columns {missing} - Planetiler version changed?")
        for line in f:
            row = line.rstrip("\n").split("\t")
            if len(row) < len(header):
                continue
            tile = (int(row[index["z"]]), int(row[index["x"]]), int(row[index["y"]]))
            layer = row[index["layer"]]
            # Planetiler emits a summary row with an empty layer name per
            # tile; the per-layer rows are what this compares.
            if layer:
                stats[tile][layer] = {field: int(row[index[field]]) for field in STAT_FIELDS}
    return dict(stats)


def merge_shard_stats(shards: list[dict[Tile, dict[str, dict[str, int]]]]) -> tuple[dict, set[Tile]]:
    """Union of the shards' layer stats, plus the set of tiles more than one
    shard produced.

    Overlap is a finding in its own right and never silently merged: the
    design's claim is that shards are DISJOINT, so combining them is
    concatenation. A tile two shards both wrote means that claim is false
    there, and which copy won would decide what a hiker sees."""
    merged: dict[Tile, dict[str, dict[str, int]]] = {}
    overlaps: set[Tile] = set()
    for shard in shards:
        for tile, layers in shard.items():
            if tile in merged:
                overlaps.add(tile)
                continue
            merged[tile] = layers
    return merged, overlaps


def compare_stats(control: dict, sharded: dict) -> list[Difference]:
    """Every (tile, layer, metric) disagreement, control as the reference.

    Ordered by tile then layer then metric so a diff of two runs of this
    script is itself readable - the output is meant to be pasted into an
    issue and compared against the next attempt."""
    differences = []
    for tile in sorted(set(control) | set(sharded)):
        control_layers, sharded_layers = control.get(tile), sharded.get(tile)
        if sharded_layers is None:
            differences.append(Difference(tile, None, None, 1, None))
            continue
        if control_layers is None:
            differences.append(Difference(tile, None, None, None, 1))
            continue
        for layer in sorted(set(control_layers) | set(sharded_layers)):
            here, there = control_layers.get(layer), sharded_layers.get(layer)
            for metric in STAT_FIELDS:
                a = None if here is None else here[metric]
                b = None if there is None else there[metric]
                if a != b:
                    differences.append(Difference(tile, layer, metric, a, b))
    return differences


def tile_hashes(path: Path) -> dict[Tile, str]:
    """sha256 per tile, streamed in tile-id order.

    all_tiles() rather than a Reader.get() per tile for the same reason
    extract_package.py documents: get() re-walks the directory tree on every
    call, which turns a whole-archive pass from seconds into hours."""
    hashes: dict[Tile, str] = {}
    with open(path, "rb") as f:

        def get_bytes(offset, length):
            f.seek(offset)
            return f.read(length)

        for (z, x, y), data in all_tiles(get_bytes):
            hashes[(z, x, y)] = hashlib.sha256(data).hexdigest()
    return hashes


def compare_hashes(control: dict[Tile, str], sharded: dict[Tile, str]) -> list[Tile]:
    """Tiles present in both builds whose bytes differ.

    Presence differences are left to compare_stats(); this answers only
    "same tile or not" for the tiles both produced, which is the claim layer
    stats cannot make on their own."""
    return sorted(t for t in set(control) & set(sharded) if control[t] != sharded[t])


def to_mercator(geom_4326):
    """always_xy for the reason lib/corridor.py documents: everything here is
    (lon, lat), and pyproj's authority-order default would swap them."""
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    return transform(transformer.transform, geom_4326)


def seam_geometry(geom):
    """The cut, validated rather than converted.

    Taken as given, whatever its type: a line where shards abut, a polygon
    where they overlap - Geofabrik's .poly shapes carry a margin, so the band
    both shards were asked to produce is an area, not a line. Converting a
    polygon to its boundary here (an earlier version did) turns that band
    into its outline and quietly measures the wrong thing.

    The empty check is not defensive padding. An empty geometry's bounds are
    (nan, nan, nan, nan), which reaches the tile arithmetic and fails as
    `cannot convert float NaN to integer` - a stack trace three frames from
    anything that names the seam."""
    if geom.is_empty:
        raise SystemExit("The seam geometry is empty - the shards may not touch, or the wrong file was passed.")
    return geom


def seam_tiles(seam_merc, zoom: int) -> set[tuple[int, int]]:
    """Tiles at `zoom` that the seam touches.

    Works for a line or an area: a tile is at the seam if the cut passes
    through it, and for an overlap band that means any tile the band covers -
    which is exactly the set both shards were asked to produce."""
    prepared = prep(seam_merc)
    x0, x1, y0, y1 = tile_range_for_bounds(seam_merc.bounds, zoom)
    return {
        (x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if prepared.intersects(box(*tile_bounds_merc(zoom, x, y)))
    }


def attribute(differing_tiles: list[Tile], overlaps: set[Tile]) -> tuple[list[Tile], list[Tile]]:
    """Split differing tiles by whether one shard produced them or two.

    This is what makes the difference count readable. A tile two shards both
    produced is one where THE MERGE RULE chose what survived - each shard saw
    only its own side of it, so of course the kept copy differs from the
    control. That says nothing about whether Planetiler ranks features
    globally; it says the shards are not tile-disjoint, which is a separate
    (and expected, at low zoom) finding.

    Only the tiles exactly one shard produced can indict the build itself."""
    single = [t for t in differing_tiles if t not in overlaps]
    shared = [t for t in differing_tiles if t in overlaps]
    return single, shared


def distance_to_seam(tile: Tile, seam_at_zoom: set[tuple[int, int]], max_distance: int = MAX_SEAM_DISTANCE) -> int | None:
    """Chebyshev distance in tiles from `tile` to the nearest seam tile, or
    None past `max_distance`.

    Ring-by-ring outward rather than scanning every seam tile: the answer is
    almost always 0-2, and a state boundary at z14 is thousands of seam
    tiles that a brute-force nearest would touch for every difference."""
    z, x, y = tile
    if (x, y) in seam_at_zoom:
        return 0
    for radius in range(1, max_distance + 1):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                # Only the ring itself - the interior was covered by a
                # smaller radius, and re-testing it is the whole cost.
                if max(abs(dx), abs(dy)) == radius and (x + dx, y + dy) in seam_at_zoom:
                    return radius
    return None


def seam_distance_histogram(tiles: list[Tile], seam_by_zoom: dict[int, set[tuple[int, int]]]) -> Counter:
    """How far each differing tile sits from the seam, as {distance: count}
    with None for "further than MAX_SEAM_DISTANCE"."""
    return Counter(distance_to_seam(t, seam_by_zoom.get(t[0], set())) for t in tiles)


def verdict(histogram: Counter, padding_tiles: int = 2) -> str:
    """The one-line reading of the histogram.

    `padding_tiles` is the width, in tiles, inside which a difference is
    explainable as a shard's input stopping too close to its output. Two is
    deliberately generous for a first run - the point of the histogram is
    that a wrong threshold is visible rather than baked into a verdict."""
    if not histogram:
        return "LOSSLESS: no tile differs between the control build and the shards."
    beyond = sum(count for distance, count in histogram.items() if distance is None or distance > padding_tiles)
    if beyond == 0:
        return f"SEAM-LOCAL: every difference is within {padding_tiles} tiles of the cut - a padding problem, and padding is a parameter."
    return (
        f"NOT SEAM-LOCAL: {beyond} difference(s) sit deeper than {padding_tiles} tiles inside a shard. "
        "Padding cannot explain those - suspect a feature whose fate Planetiler decides from the whole input."
    )


def report(control_dir: Path, shard_dirs: list[Path], seam_path: Path | None, padding_tiles: int) -> int:
    """Print the comparison. Returns the number of differing tiles, which is
    the number a run wants to drive to zero."""
    control_stats = read_layer_stats(control_dir / "build.pmtiles.layerstats.tsv.gz")
    sharded_stats, overlaps = merge_shard_stats([read_layer_stats(d / "build.pmtiles.layerstats.tsv.gz") for d in shard_dirs])

    differences = compare_stats(control_stats, sharded_stats)
    control_hashes = tile_hashes(control_dir / "build.pmtiles")
    sharded_hashes: dict[Tile, str] = {}
    for d in shard_dirs:
        sharded_hashes.update(tile_hashes(d / "build.pmtiles"))
    byte_differs = compare_hashes(control_hashes, sharded_hashes)

    print(f"Control tiles: {len(control_hashes)}   Sharded tiles: {len(sharded_hashes)}")
    if overlaps:
        print(f"\n!! {len(overlaps)} tile(s) were produced by more than one shard - the shards are NOT disjoint.")
        for tile in sorted(overlaps)[:10]:
            print(f"   z{tile[0]}/{tile[1]}/{tile[2]}")

    by_kind = Counter(d.kind for d in differences)
    print(f"\nLayer-stat differences: {len(differences)} across {len({d.tile for d in differences})} tile(s) {dict(by_kind)}")
    by_layer = Counter(f"{d.layer}.{d.metric}" for d in differences if d.metric)
    for name, count in by_layer.most_common(15):
        print(f"   {name:44s} {count}")

    print(f"\nTiles whose bytes differ: {len(byte_differs)}")

    differing_tiles = sorted({d.tile for d in differences} | set(byte_differs))
    print("\nDiffering tiles by zoom:")
    for zoom, count in sorted(Counter(t[0] for t in differing_tiles).items()):
        print(f"   z{zoom:<3} {count}")

    # The attribution that makes the count above mean something.
    single, shared = attribute(differing_tiles, overlaps)
    print(f"\n{len(shared)} of {len(differing_tiles)} differing tile(s) were produced by MORE THAN ONE shard.")
    print("   Those are the merge rule's doing, not the build's: each shard saw one side, and first-wins kept one of them.")
    print(f"{len(single)} differ on a tile exactly ONE shard produced.")
    print("   Only these can indict the build - they are what the verdict below is computed on.")

    if seam_path is None:
        print("\nNo --seam given, so no distance histogram - that is the reading that matters; pass one.")
        return len(differing_tiles)

    seam_merc = to_mercator(seam_geometry(shape(_geometry_of(seam_path))))
    seam_by_zoom = {z: seam_tiles(seam_merc, z) for z in {t[0] for t in single}}
    histogram = seam_distance_histogram(single, seam_by_zoom)

    print("\nDistance from the cut, in tiles (single-shard differences only):")
    for distance in sorted(histogram, key=lambda d: (d is None, d)):
        label = f">{MAX_SEAM_DISTANCE}" if distance is None else str(distance)
        print(f"   {label:>3} tile(s) away: {histogram[distance]}")
    print(f"\n{verdict(histogram, padding_tiles)}")
    return len(differing_tiles)


def _geometry_of(path: Path):
    """GeoJSON geometry from a bare Geometry, a Feature, or the first member
    of a FeatureCollection - the same three shapes extract_package.py's
    --region accepts, so the seam can be any file already lying around."""
    import json

    parsed = json.loads(path.read_text())
    if parsed.get("type") == "FeatureCollection":
        return parsed["features"][0]["geometry"]
    if parsed.get("type") == "Feature":
        return parsed["geometry"]
    return parsed


def main(args: argparse.Namespace) -> None:
    differing = report(args.control, args.shard, args.seam, args.padding_tiles)
    if args.fail_on_difference and differing:
        raise SystemExit(f"{differing} tile(s) differ between the control build and the shards.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--control", type=Path, required=True, help="Directory holding the whole-region build.pmtiles and its layerstats"
    )
    parser.add_argument("--shard", type=Path, action="append", required=True, help="A shard's directory; repeat once per shard")
    parser.add_argument(
        "--seam", type=Path, default=None, help="GeoJSON polygon whose BOUNDARY is the cut, for the distance histogram"
    )
    parser.add_argument(
        "--padding-tiles",
        type=int,
        default=2,
        help="Width in tiles inside which a difference counts as seam-local (default: %(default)s)",
    )
    parser.add_argument(
        "--fail-on-difference", action="store_true", help="Exit non-zero if anything differs (off by default: a spike measures)"
    )
    main(parser.parse_args())
