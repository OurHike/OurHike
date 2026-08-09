"""Photo-scope sizing spike (features/PHOTO_DOWNLOADS.md, question Q8).

Answers one question, and only one: **what does downloading the photos for a
stretch of trail actually cost, and how much worse is the worst stretch than
the average one?**

PHOTO_DOWNLOADS.md's Finding 2 sizes a scope by dividing the corpus by the
length of the trail - ~32.5 KB per mile today. That is an average, and photos
are not spread evenly: they sit where shelters and campsites sit, which
clusters. A ceiling on an automatic download (Finding 4) chosen against the
mean is a ceiling that quietly refuses to fetch the sections that cluster
hardest, which is a bad failure to discover in the field rather than here.

So this measures the distribution rather than the mean:

  - the real corpus totals, from real file sizes on disk,
  - bytes per rolling window of several lengths - p50, p95 and the worst one,
  - where the worst window is, so it can be looked at on a map.

Uses only already-fetched data (fetch_all.py, then fetch_atc_photos.py) - no
network, same as spike_day_planner.py and spike_corridor.py. Photo BYTES come
from the content-addressed cache under data/raw/poi_photos/; a digest whose
file is missing is reported and excluded rather than guessed at, because a
size budget built on a guessed size is the thing this script exists to
replace.

THIS IS A SPIKE AND THE ARITHMETIC HERE IS THROWAWAY. The real version of
this question is answered on a phone, in TypeScript, over the `mile` the
pipeline will publish on every POI (HIKE_PLANNING.md's Finding 2, which
PHOTO_DOWNLOADS.md's Phase B also depends on). What should survive is the
SHAPE - windows sampled uniformly for the distribution and anchored at photos
for the true maximum - not this code.

Ordering and projection come from export_elevation.py rather than being
re-derived, for the reason HIKE_PLANNING.md's Finding 1 gives: this
repository already measures "a mile" two different ways, and a spike that
invented a third would be measuring its own arithmetic.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import duckdb
from shapely.geometry import LineString, Point

from export_elevation import (
    GEOGRAPHIC_CRS,
    METERS_PER_MILE,
    PROJECTED_CRS,
    load_merged_trail_line,
    ordered_oriented_parts,
    reproject_lines_to_meters,
)
from fetch_atc_photos import PHOTO_LAYERS, photo_urls
from lib.photo_store import local_photo_path

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
CENTERLINE_PATH = RAW_DIR / "centerline.geojson"
ATC_OUTCOMES_PATH = RAW_DIR / "poi_images_atc.json"

# Window lengths to measure, in miles. A day, a week, and a long section -
# the three scopes PHOTO_DOWNLOADS.md's Finding 2 puts numbers against.
DEFAULT_WINDOWS_MI = (15.0, 100.0, 500.0)

# How finely the uniform sample walks the trail when building the
# distribution. Half a mile is the spacing of the pipeline's own mile-marker
# points, and it is far below the smallest window measured.
SAMPLE_STEP_MI = 0.5

# How far off the centerline a POI may sit and still count as being on this
# stretch of it. Shelters are routinely a few hundred feet down a blue blaze;
# the same bar spike_day_planner.py applies, for the same reason.
MAX_OFF_TRAIL_MI = 0.5

# ATC's GlobalID is what fetch_atc_photos.py keys its outcome records on
# (`f"{source}:{GlobalID}"`), so it is what this has to join back on.
ID_FIELD = "globalid"


@dataclass(frozen=True)
class PhotoPoi:
    """A POI with at least one photo, positioned along the trail."""

    poi_id: str
    name: str
    kind: str
    mile: float
    off_trail_mi: float
    # Bytes actually on disk for the photo that ships today.
    card_bytes: int
    # How many photos ATC carries for this POI (Photo1..Photo10). Real, read
    # from the layer - it is what #471 would ship, and the only part of the
    # --all-photos model that is measured rather than assumed.
    photo_count: int


@dataclass(frozen=True)
class WindowStats:
    window_mi: float
    p50_bytes: float
    p95_bytes: float
    max_bytes: int
    max_start_mi: float
    mean_bytes: float


def percentile(values: list[float], fraction: float) -> float:
    """The value at `fraction` through a sorted list, by nearest rank.

    Deliberately not interpolated: these are sums over a discrete set of
    windows, and inventing a value between two real ones would report a
    section size that no section has.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def window_bytes(positions: list[tuple[float, int]], start_mi: float, window_mi: float) -> int:
    """Total bytes of every photo whose mile falls in [start, start + window).

    Half-open on purpose: adjacent windows tile the trail without
    double-counting a photo that lands exactly on a boundary.
    """
    end_mi = start_mi + window_mi
    return sum(size for mile, size in positions if start_mi <= mile < end_mi)


def rolling_stats(
    positions: list[tuple[float, int]],
    window_mi: float,
    trail_miles: float,
    step_mi: float = SAMPLE_STEP_MI,
) -> WindowStats:
    """What a window of this length costs, across the whole trail.

    Two different samplings, because two different questions are being asked
    and one sampling cannot answer both honestly:

    **The distribution is sampled uniformly** along the trail, every
    `step_mi`. "What does a typical 100-mile section cost" is a question
    about sections a hiker might pick, and hikers do not pick sections that
    start exactly at a shelter.

    **The maximum is anchored at each photo's own mile**, which is where it
    provably lives: the content of a half-open window changes only when its
    start crosses a photo, so the largest window always begins at one. A
    uniform sample would under-report the worst case by up to a step, and the
    worst case is the number a ceiling gets chosen against.
    """
    if trail_miles <= 0:
        return WindowStats(window_mi, 0.0, 0.0, 0, 0.0, 0.0)

    samples: list[float] = []
    start = 0.0
    while start < trail_miles:
        samples.append(float(window_bytes(positions, start, window_mi)))
        start += step_mi

    worst_bytes = 0
    worst_start = 0.0
    for mile, _ in positions:
        total = window_bytes(positions, mile, window_mi)
        if total > worst_bytes:
            worst_bytes, worst_start = total, mile

    return WindowStats(
        window_mi=window_mi,
        p50_bytes=percentile(samples, 0.50),
        p95_bytes=percentile(samples, 0.95),
        max_bytes=worst_bytes,
        max_start_mi=worst_start,
        mean_bytes=sum(samples) / len(samples) if samples else 0.0,
    )


def modelled_bytes(poi: PhotoPoi, mean_photo_bytes: float, all_photos: bool) -> int:
    """What this POI contributes to a scope.

    Today that is one photo and a real file size. Under --all-photos it is
    every photo ATC carries for it (#471), and only the COUNT is measured -
    the extra photos have never been downloaded, so their bytes are the mean
    of the ones that have. Stated rather than hidden: this is the one
    estimated number in the script, it is applied to a real count, and the
    corpus mean it uses is itself measured from real files.
    """
    if not all_photos:
        return poi.card_bytes
    extras = max(0, poi.photo_count - 1)
    return poi.card_bytes + round(extras * mean_photo_bytes)


def load_photo_sizes(outcomes_path: Path, raw_dir: Path) -> tuple[dict[str, int], list[str]]:
    """Every POI id with a downloaded photo, mapped to that photo's real byte
    size on disk, plus the ids whose bytes have gone missing.

    A missing file is reported rather than dropped silently or estimated: it
    means the cache was cleared under an outcomes file that still claims the
    photo, which makes every total below quietly low. The caller decides what
    to do about it; this only refuses to guess.
    """
    outcomes = json.loads(outcomes_path.read_text(encoding="utf-8")).get("pois", {})
    sizes: dict[str, int] = {}
    missing: list[str] = []
    for poi_id, record in outcomes.items():
        if record.get("status") != "found":
            continue
        digest = (record.get("photo") or {}).get("digest")
        if not digest:
            continue
        path = local_photo_path(raw_dir, digest)
        if path.exists():
            sizes[poi_id] = path.stat().st_size
        else:
            missing.append(poi_id)
    return sizes, missing


def read_photo_features(con: duckdb.DuckDBPyConnection, path: Path, source: str) -> list[tuple[str, str, int, Point]]:
    """Every feature in an ATC layer that carries a photo reference, as
    (poi_id, name, photo_count, projected point).

    The photo COUNT comes from the layer rather than from the outcomes file,
    because it is what #471 would ship and the outcomes file only ever
    recorded the one photo that was kept.

    always_xy on the transform for the reason README.md's "Gotcha hit and
    fixed" note gives: without it PROJ silently swaps the axes rather than
    erroring, and the failure surfaces much later as nonsense distances.
    """
    features = json.loads(path.read_text(encoding="utf-8")).get("features", [])
    counts: dict[str, tuple[str, int]] = {}
    for feature in features:
        properties = feature.get("properties") or {}
        urls = photo_urls(properties)
        feature_id = properties.get("GlobalID") or feature.get("id")
        if urls and feature_id:
            counts[str(feature_id)] = (str(properties.get("Name") or feature_id), len(urls))

    con.execute(f"CREATE OR REPLACE TABLE _photo_layer AS SELECT * FROM ST_Read('{path.as_posix()}')")
    columns = [row[1].lower() for row in con.execute("PRAGMA table_info('_photo_layer')").fetchall()]
    if ID_FIELD not in columns:
        return []

    rows = con.execute(f"""
        SELECT "{ID_FIELD}",
               ST_X(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true)),
               ST_Y(ST_Transform(geom, '{GEOGRAPHIC_CRS}', '{PROJECTED_CRS}', always_xy := true))
        FROM _photo_layer
        WHERE geom IS NOT NULL
    """).fetchall()

    found = []
    for feature_id, x, y in rows:
        entry = counts.get(str(feature_id))
        if entry is None or x is None or y is None:
            continue
        name, count = entry
        found.append((f"{source}:{feature_id}", name, count, Point(x, y)))
    return found


def locate(
    parts_meters: list[LineString],
    features: list[tuple[str, str, int, Point]],
    kind: str,
    sizes: dict[str, int],
) -> list[PhotoPoi]:
    """Position each photo-bearing POI along the ordered centerline, in miles
    from the southern terminus.

    The same measurement export_elevation.py's `distance_mi` is: cumulative
    length along the ordered, oriented, merged pieces. A feature with no
    downloaded photo is skipped - it has no bytes to contribute, so it is not
    part of what a scope costs.
    """
    offsets: list[float] = []
    running = 0.0
    for part in parts_meters:
        offsets.append(running)
        running += part.length

    located: list[PhotoPoi] = []
    for poi_id, name, count, point in features:
        card_bytes = sizes.get(poi_id)
        if card_bytes is None:
            continue
        best = min(range(len(parts_meters)), key=lambda i: parts_meters[i].distance(point))
        part = parts_meters[best]
        located.append(
            PhotoPoi(
                poi_id=poi_id,
                name=name,
                kind=kind,
                mile=(offsets[best] + part.project(point)) / METERS_PER_MILE,
                off_trail_mi=part.distance(point) / METERS_PER_MILE,
                card_bytes=card_bytes,
                photo_count=count,
            )
        )
    return sorted(located, key=lambda p: p.mile)


def megabytes(value: float) -> str:
    return f"{value / 1_000_000:.1f} MB"


def kilobytes(value: float) -> str:
    return f"{value / 1_000:.0f} KB"


def report(pois: list[PhotoPoi], trail_miles: float, windows: list[float], all_photos: bool) -> None:
    mean_photo_bytes = sum(p.card_bytes for p in pois) / len(pois) if pois else 0.0
    positions = [(p.mile, modelled_bytes(p, mean_photo_bytes, all_photos)) for p in pois]
    total_bytes = sum(size for _, size in positions)
    total_photos = sum(p.photo_count if all_photos else 1 for p in pois)

    print()
    print(f"Corpus ({'every ATC photo, #471' if all_photos else 'the card photo only, as published today'})")
    print(f"  POIs with a photo          {len(pois)}")
    print(f"  photos                     {total_photos}")
    print(f"  mean bytes per photo       {kilobytes(mean_photo_bytes)} (measured, on disk)")
    print(f"  whole trail                {megabytes(total_bytes)} over {trail_miles:.0f} mi")
    print(f"  average per trail mile     {kilobytes(total_bytes / trail_miles) if trail_miles else 'n/a'}")

    print()
    print("What a scope costs. p50/p95 are windows sampled uniformly every")
    print(f"{SAMPLE_STEP_MI} mi; max is the worst window anywhere on the trail.")
    print()
    print(f"  {'window':>10}  {'p50':>10}  {'p95':>10}  {'worst':>10}  {'worst starts at':>16}  {'worst/mean':>10}")
    for window_mi in windows:
        stats = rolling_stats(positions, window_mi, trail_miles)
        ratio = stats.max_bytes / stats.mean_bytes if stats.mean_bytes else 0.0
        print(
            f"  {stats.window_mi:>8.0f}mi  {megabytes(stats.p50_bytes):>10}  {megabytes(stats.p95_bytes):>10}"
            f"  {megabytes(stats.max_bytes):>10}  {'mi ' + format(stats.max_start_mi, '.1f'):>16}  {ratio:>9.1f}x"
        )

    print()
    print("Finding 4's default 10 MB ceiling, against these windows:")
    for window_mi in windows:
        stats = rolling_stats(positions, window_mi, trail_miles)
        verdict = "fits everywhere" if stats.max_bytes <= 10_000_000 else "refused on the worst sections"
        print(f"  {window_mi:>6.0f} mi   {verdict}")


def main(windows: list[float], all_photos: bool) -> int:
    for path in (CENTERLINE_PATH, ATC_OUTCOMES_PATH):
        if not path.exists():
            print(f"Missing {path} - run fetch_all.py and fetch_atc_photos.py first.")
            return 1

    sizes, missing = load_photo_sizes(ATC_OUTCOMES_PATH, RAW_DIR)
    if not sizes:
        print(f"{ATC_OUTCOMES_PATH} records no downloaded photos - nothing to measure.")
        return 1
    if missing:
        print(f"{len(missing)} POIs claim a photo whose bytes are not in the cache; excluded.")
        print("  (a cleared data/ tree - re-run fetch_atc_photos.py, or every total below is low)")

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    parts = ordered_oriented_parts(load_merged_trail_line(con, CENTERLINE_PATH))
    parts_meters = reproject_lines_to_meters(con, parts)
    trail_miles = sum(part.length for part in parts_meters) / METERS_PER_MILE

    located: list[PhotoPoi] = []
    for stem, source in PHOTO_LAYERS:
        path = RAW_DIR / f"{stem}.geojson"
        if not path.exists():
            print(f"Missing {path}; skipping {source}.")
            continue
        located.extend(locate(parts_meters, read_photo_features(con, path, source), source, sizes))

    far = [p for p in located if p.off_trail_mi > MAX_OFF_TRAIL_MI]
    if far:
        print(f"{len(far)} photo POIs sit more than {MAX_OFF_TRAIL_MI} mi off the centerline; excluded.")
    on_trail = sorted((p for p in located if p.off_trail_mi <= MAX_OFF_TRAIL_MI), key=lambda p: p.mile)

    if not on_trail:
        print("No photo-bearing POIs could be placed on the centerline.")
        return 1

    report(on_trail, trail_miles, windows, all_photos)
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--windows",
        default=",".join(str(w) for w in DEFAULT_WINDOWS_MI),
        help="Comma-separated scope lengths to measure, in miles.",
    )
    parser.add_argument(
        "--all-photos",
        action="store_true",
        help="Model #471's full corpus - every ATC photo per POI, not just the one shipped today.",
    )
    args = parser.parse_args(argv)
    windows = [float(part) for part in args.windows.split(",") if part.strip()]
    return main(windows, args.all_photos)


if __name__ == "__main__":
    raise SystemExit(run())
