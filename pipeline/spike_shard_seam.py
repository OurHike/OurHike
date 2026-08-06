"""Build one region three ways, so the sharded-build design in BASEMAP.md
can be believed or abandoned on evidence (#194).

BASEMAP.md's continental plan splits the high zooms across free runners, one
Geofabrik sub-region each, and never reconciles them - the shards are meant
to be disjoint, so combining them is concatenation. Two things are asserted
there and measured here:

  1. That a tile built inside a shard is the tile the whole-region build
     would have produced.
  2. That Planetiler's temp disk really is ~5x its input, the number the
     whole "every sub-region fits a free runner" table rests on. Planetiler's
     own planet guidance says 10x, and nobody has watched the directory.

## Why three builds and not two

A single shard-vs-control comparison cannot tell the two failure modes
apart, and they have opposite consequences:

  CONTROL      the region built whole, bounded to the union of the two
               shard shapes so its tile set matches theirs exactly.

  ARM A        each shard gets the WHOLE region's PBF as input and differs
  polygon-only from the control in nothing but --polygon. Any difference
               here cannot be missing data, because no data is missing -
               it can only be Planetiler deciding something from the extent
               of what it was asked to output. That is the failure mode no
               amount of padding fixes, and the one BASEMAP.md flags as
               unproved.

  ARM B        each shard gets only its own state's extract, the way a real
  realistic    sharded build would run. Differences here that are NOT in
               arm A are the padding requirement, and the seam-distance
               histogram says how wide it has to be.

Arm A is the experiment; arm B is the deployment. Running only arm B would
find differences and leave their cause ambiguous, which is exactly the
ambiguity this exists to remove.

Two adjacent states rather than a synthetic split, because the seam has to
be a real one: Geofabrik cuts its extracts on administrative boundaries, so
a state border is the shape of cut a continental build would actually make.
The default pair is Vermont and New Hampshire - adjacent, both small enough
to iterate on, and sharing a border that is a river with roads and towns on
both sides, which is where a cut does damage if it does any.

Nothing here publishes, and nothing here is on the critical path of a
release; it is a measurement whose output is a number for BASEMAP.md and a
comment on #194.
"""

import argparse
import json
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from shapely.geometry import mapping

from export_basemap import GEOFABRIK_BASE, osmium_merge_cmd, planetiler_cmd
from lib.poly import from_poly, to_poly

ROOT = Path(__file__).parent
WORK_DIR = ROOT / "data" / "shard-spike"

DEFAULT_STATES = ("vermont", "new-hampshire")

# How often the temp directory is measured while Planetiler runs. Planetiler
# deletes intermediates as phases end, so the peak is a moment rather than
# the final size - too slow a poll and the number read is whatever survived,
# which is exactly the mistake that makes 5x look true when it is not.
DISK_POLL_SECONDS = 2.0


@dataclass
class BuildResult:
    name: str
    directory: Path
    input_bytes: int
    output_bytes: int
    peak_tmp_bytes: int
    peak_apparent_bytes: int
    seconds: float

    @property
    def disk_multiplier(self) -> float:
        return self.peak_tmp_bytes / self.input_bytes if self.input_bytes else 0.0

    @property
    def apparent_multiplier(self) -> float:
        return self.peak_apparent_bytes / self.input_bytes if self.input_bytes else 0.0


# Two numbers because the first run of this spike reported the wrong one and
# it looked plausible. Planetiler's node map is a SPARSE file: it is created
# at the size of the node-ID space and only the pages it touches are ever
# allocated. st_size therefore reads the same ~2 GB for every build no matter
# how big its input is - which is exactly what happened, and 19.5x, 19.5x,
# 19.5x, 49.2x, 31.7x across five different inputs is the shape of a constant
# being divided by five different denominators, not a measurement.
#
# st_blocks is what the runner's free space actually loses. Apparent size is
# kept alongside it because the gap between them IS the finding: anyone
# sizing a machine off `ls -l` or a naive walk will over-provision wildly.


def directory_bytes(path: Path) -> int:
    """Disk actually consumed under `path` - allocated blocks, not apparent
    size - and 0 if it does not exist yet.

    st_blocks is in 512-byte units by POSIX definition regardless of the
    filesystem's own block size. Walked in Python rather than shelling to
    `du` so the sampler cannot be the thing that fails a build."""
    if not path.exists():
        return 0
    return sum(f.stat().st_blocks * 512 for f in path.rglob("*") if f.is_file())


def directory_apparent_bytes(path: Path) -> int:
    """What a naive walk (or `ls -l`, or `du --apparent-size`) would report.

    Kept only to print beside the real number, so the sparse-file gap is
    visible in the output rather than something the next person rediscovers."""
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def measure_both(path: Path) -> tuple[int, int]:
    """(allocated, apparent) in one walk."""
    return directory_bytes(path), directory_apparent_bytes(path)


class PeakDiskSampler:
    """Watches a directory's size while something else fills it.

    A context manager rather than a callback because the thing being measured
    is a subprocess we block on, and the peak has to be taken from another
    thread or it is only ever the size after the process exits."""

    def __init__(self, path: Path, interval: float = DISK_POLL_SECONDS, measure=measure_both):
        self.path, self.interval = path, interval
        self.peak, self.peak_apparent = 0, 0
        # Injectable so the peak-keeping logic can be tested by driving
        # sample() directly, instead of by racing a real thread against a
        # directory and hoping the poll lands where the test needs it.
        self._measure = measure
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def sample(self) -> int:
        """Take one measurement and fold both peaks in.

        The two are tracked independently rather than as one reading: they
        need not peak at the same instant, and taking the apparent size from
        whichever moment the allocated size peaked would understate it."""
        allocated, apparent = self._measure(self.path)
        self.peak = max(self.peak, allocated)
        self.peak_apparent = max(self.peak_apparent, apparent)
        return self.peak

    def _run(self):
        while not self._stop.is_set():
            self.sample()
            self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=self.interval * 2)
        # A final sample so a build shorter than one poll interval is still
        # measured rather than reported as zero.
        self.sample()
        return False


def fetch(url: str, dest: Path) -> Path:
    """Skip-if-present, for the same reason export_basemap.py's fetch does:
    Geofabrik republishes daily so a conditional request buys nothing, and a
    re-run of this spike on a warm checkout should not re-download."""
    if dest.exists():
        print(f"  {dest.name}: already present ({dest.stat().st_size / 1e6:.0f} MB)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  {dest.name}: fetching {url}")
    with requests.get(url, stream=True, timeout=900) as resp:
        resp.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    print(f"  {dest.name}: {dest.stat().st_size / 1e6:.0f} MB")
    return dest


def seam_between(shapes: list) -> object:
    """The cut: where the shard shapes meet each other.

    Never the outline of either shard - a shard's outer edge is the region's
    edge, cut identically in the control, so no difference there can be
    blamed on sharding.

    Geofabrik's published .poly shapes OVERLAP rather than abut. Each is the
    state boundary with a margin, so features near the line arrive whole in
    both extracts. Two overlapping polygons share no boundary LINE - their
    outlines cross at a handful of points - which is why the first run that
    got this far died on `cannot convert float NaN to integer`: the
    point-set intersection has an empty boundary and empty bounds are NaN.

    So the overlap zone IS the seam where one exists, and it is a truer one
    than a line would be: every tile in that band is a tile both shards were
    asked to produce. The shared-border line is the fallback for shapes that
    genuinely abut."""
    overlap, border = None, None
    for i, a in enumerate(shapes):
        for b in shapes[i + 1 :]:
            shared_area = a.intersection(b)
            if not shared_area.is_empty and shared_area.area > 0:
                overlap = shared_area if overlap is None else overlap.union(shared_area)
                continue
            touching = a.boundary.intersection(b.boundary)
            if not touching.is_empty:
                border = touching if border is None else border.union(touching)

    seam = overlap if overlap is not None else border
    if seam is None or seam.is_empty:
        raise SystemExit("The chosen regions neither overlap nor share a border - there is no seam to measure.")
    return seam


# Planetiler's own default is 30s, and that is what expired. Its internal
# --http-retries=5 did not outlast the host either, so the outer retry here
# is a third belt rather than a duplicate: Planetiler retries the request,
# this retries the whole invocation minutes later.
HTTP_TIMEOUT_SECONDS = 300


def download_sources_cmd(jar: Path, osm_pbf: Path, tmp_dir: Path) -> list[str]:
    """Fetch the profile's non-OSM sources and stop, without building.

    A step of its own because those ~1.4 GB come from three third parties and
    have now failed a run twice, in the middle of a measurement they have
    nothing to do with. Pulling them first means the flaky part happens once,
    before any timing starts, where CI can cache the result and where a
    failure is unambiguously about the network rather than about sharding.

    --only-download is Planetiler's own flag for this (`download source data
    then exit`); the output path is required but never written."""
    return [
        "java",
        "-jar",
        str(jar),
        f"--osm-path={osm_pbf}",
        f"--tmpdir={tmp_dir}",
        f"--http-timeout={HTTP_TIMEOUT_SECONDS}s",
        "--only-download",
        "--download",
    ]


def run_planetiler(cmd: list[str], attempts: int = 3, sleep=time.sleep, run=subprocess.run) -> int:
    """Run Planetiler, retrying a failed attempt. Returns the attempt that
    worked; re-raises if none did.

    Here because a run died on `Error getting size of
    water-polygons-split-3857.zip ... TimeoutException` - Planetiler fetching
    a 928 MB shapefile from a third party that had served it fine ten minutes
    earlier. That is weather, not a result, and a spike that reports failure
    when osmdata.openstreetmap.de is slow teaches nothing about sharding.

    Retrying is cheap and safe: downloaded sources are cached under
    data/sources so a second attempt skips what already arrived, and --force
    means a half-written output is overwritten rather than appended to."""
    for attempt in range(1, attempts + 1):
        try:
            run(cmd, check=True)
            return attempt
        except subprocess.CalledProcessError:
            if attempt == attempts:
                raise
            delay = 15 * attempt
            print(f"  attempt {attempt}/{attempts} failed; retrying in {delay}s", flush=True)
            sleep(delay)
    raise AssertionError("unreachable")


def fit_fixed_and_marginal(points: list[tuple[int, int]]) -> tuple[float, float]:
    """Least-squares (fixed_bytes, marginal_multiplier) for peak = fixed + k*input.

    The whole reason the first disk answer was wrong. Planetiler pays a cost
    that does not scale with the input - profile-derived intermediates, the
    node map's floor - and at VT/NH scale that cost WAS the measurement: five
    builds all peaked at 0.85 GB, so "7.4x" and "18.6x" were one constant over
    five denominators.

    BASEMAP.md's fits-a-free-runner table needs the MARGINAL rate, because
    that is what grows when the region does. Two points separate it from the
    fixed cost; three make the line worth believing."""
    if len(points) < 2:
        raise ValueError("Need at least two builds of different sizes to separate fixed cost from marginal rate")
    n = len(points)
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    denominator = n * sxx - sx * sx
    if denominator == 0:
        raise ValueError("All builds had the same input size - that cannot separate fixed cost from marginal rate")
    marginal = (n * sxy - sx * sy) / denominator
    fixed = (sy - marginal * sx) / n
    return fixed, marginal


def run_build(name: str, work: Path, jar: Path, osm_pbf: Path, poly_path: Path | None, max_zoom: int) -> BuildResult:
    """One Planetiler build into its own directory, with the temp directory
    watched throughout.

    Every build writes `build.pmtiles` under its own directory so
    compare_shards.py can take directories rather than a naming convention
    that has to agree in two places."""
    out_dir = work / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path, tmp_dir = out_dir / "build.pmtiles", out_dir / "tmp"
    cmd = planetiler_cmd(
        jar, osm_pbf, out_path, max_zoom, poly_path, tmp_dir, layer_stats=True, http_timeout_seconds=HTTP_TIMEOUT_SECONDS
    )
    print(f"\n=== {name} ===\n  {' '.join(str(c) for c in cmd)}")

    started = time.monotonic()
    with PeakDiskSampler(tmp_dir) as sampler:
        run_planetiler(cmd)
    elapsed = time.monotonic() - started

    stats_path = out_path.with_name(out_path.name + ".layerstats.tsv.gz")
    if not stats_path.exists():
        raise SystemExit(f"{name}: Planetiler wrote no layer stats at {stats_path} - the comparison has nothing to read.")

    result = BuildResult(
        name, out_dir, osm_pbf.stat().st_size, out_path.stat().st_size, sampler.peak, sampler.peak_apparent, elapsed
    )
    print(
        f"  {name}: input {result.input_bytes / 1e9:.2f} GB -> output {result.output_bytes / 1e9:.2f} GB "
        f"in {elapsed / 60:.1f} min, peak temp {result.peak_tmp_bytes / 1e9:.2f} GB ({result.disk_multiplier:.1f}x input); "
        f"apparent {result.peak_apparent_bytes / 1e9:.2f} GB ({result.apparent_multiplier:.1f}x)"
    )
    return result


def run_determinism_probe(args: argparse.Namespace, raw: Path) -> None:
    """Build the SAME input twice, identically, and compare the results.

    The noise floor, and the control this experiment should have had from the
    start. Without it, "5,438 tiles differ between control and shards" cannot
    be told apart from "5,438 tiles differ between any two Planetiler runs" -
    and the dense New York/New Jersey run made that ambiguity impossible to
    ignore: it reported 329 layer-stat differences across 136 tiles while
    5,438 tiles differed in BYTES. Content that really changed would move its
    layer stats. Bytes moving on their own, at forty times the rate, is the
    signature of encoding order rather than of sharding.

    Vermont and New Hampshire hid this because their two counts agreed (35
    and 35). Density is what separated them, which fits: more features per
    tile, more parallel work per tile, more chance that two runs serialise
    the same features in a different order.

    Whatever this probe reports is the floor beneath every other number the
    spike produces. If it is not zero, the byte comparison is measuring
    Planetiler's thread scheduling and the layer stats are the only evidence
    worth reading."""
    name = args.states[0]
    print(f"Determinism probe: building {name} twice, identically.\n", flush=True)
    pbf = fetch(f"{args.geofabrik_base}/{name}-latest.osm.pbf", raw / f"{name}.osm.pbf")

    print("\nDownloading Planetiler's profile sources (once, before any timing)...", flush=True)
    run_planetiler(download_sources_cmd(args.planetiler_jar, pbf, args.work_dir / "download-tmp"))

    for run in ("determinism-a", "determinism-b"):
        run_build(run, args.work_dir, args.planetiler_jar, pbf, None, args.max_zoom)

    print(
        "\n\nTwo builds of identical input with identical flags. Every difference the comparison\n"
        "below reports is noise - Planetiler disagreeing with itself - and is the floor beneath\n"
        "every seam number this spike has produced."
    )


def run_disk_probe(args: argparse.Namespace, raw: Path) -> None:
    """Build each named region ALONE, at increasing input size, and fit the
    line through the results.

    No shards, no arms, no comparison - this answers only the temp-disk
    question, and it answers it the way the seam experiment could not. VT/NH
    inputs (0.05-0.12 GB) are smaller than Planetiler's own fixed overhead, so
    every multiplier taken from them was that overhead in disguise. Regions
    big enough to dwarf it make the marginal rate visible.

    Bounded by the input PBF's own extent rather than a --polygon: the input
    IS the region here, which is exactly what a real sharded build does."""
    print(f"Disk probe over {len(args.states)} region(s), smallest first.\n", flush=True)
    pbfs = [fetch(f"{args.geofabrik_base}/{name}-latest.osm.pbf", raw / f"{name}.osm.pbf") for name in args.states]

    print("\nDownloading Planetiler's profile sources (once, before any timing)...", flush=True)
    run_planetiler(download_sources_cmd(args.planetiler_jar, pbfs[0], args.work_dir / "download-tmp"))

    results = [
        run_build(f"disk-{name}", args.work_dir, args.planetiler_jar, pbf, None, args.max_zoom)
        for name, pbf in zip(args.states, pbfs)
    ]

    print("\n\n=== Temp disk against input size ===")
    print(f"{'build':24s} {'input':>10s} {'peak (real)':>12s} {'ratio':>8s} {'minutes':>8s}")
    for r in results:
        print(
            f"{r.name:24s} {r.input_bytes / 1e9:9.2f}G {r.peak_tmp_bytes / 1e9:11.2f}G "
            f"{r.disk_multiplier:7.1f}x {r.seconds / 60:8.1f}"
        )

    points = [(r.input_bytes, r.peak_tmp_bytes) for r in results]
    if len({x for x, _ in points}) < 2:
        print("\nOnly one input size - cannot separate fixed cost from marginal rate.")
        return
    fixed, marginal = fit_fixed_and_marginal(points)
    print(f"\nFitted: peak temp = {fixed / 1e9:.2f} GB fixed + {marginal:.1f}x input")
    print(
        "The multiplier that matters for sizing a machine is the MARGINAL one - the fixed part does not\n"
        "grow when the region does. BASEMAP.md assumes 5x and treats Planetiler's 10x planet guidance as\n"
        f"the pessimistic bound; this run puts the marginal rate at {marginal:.1f}x."
    )
    for gb in (11.2, 17.9):
        need = (fixed + marginal * gb * 1e9) / 1e9
        print(f"  Extrapolated for a {gb:.1f} GB input: {need:.0f} GB of temp disk (+ input + output) against 88 GB free")


def main(args: argparse.Namespace) -> None:
    work = args.work_dir
    raw = work / "raw"
    work.mkdir(parents=True, exist_ok=True)

    if args.mode == "disk":
        return run_disk_probe(args, raw)
    if args.mode == "determinism":
        return run_determinism_probe(args, raw)

    print(f"Fetching {len(args.states)} extracts and their .poly shapes...")
    pbfs, shapes = [], []
    for state in args.states:
        pbfs.append(fetch(f"{args.geofabrik_base}/{state}-latest.osm.pbf", raw / f"{state}.osm.pbf"))
        poly = fetch(f"{args.geofabrik_base}/{state}.poly", raw / f"{state}.poly")
        shapes.append(from_poly(poly.read_text()))

    # Each shard's own shape, and the union that bounds the control. The
    # control MUST be bounded to the union or it produces edge tiles no shard
    # was asked for, and every one of them reads as a difference.
    shard_polys = []
    for state, geom in zip(args.states, shapes):
        path = raw / f"{state}-shard.poly"
        path.write_text(to_poly(geom, name=state))
        shard_polys.append(path)
    union = shapes[0]
    for geom in shapes[1:]:
        union = union.union(geom)
    union_poly = raw / "union.poly"
    union_poly.write_text(to_poly(union, name="control"))

    seam_path = work / "seam.geojson"
    seam_path.write_text(json.dumps(mapping(seam_between(shapes))))
    print(f"\nSeam -> {seam_path}")

    merged = raw / "merged.osm.pbf"
    if not merged.exists():
        print("Merging the state extracts into one control input...")
        subprocess.run(osmium_merge_cmd(pbfs, merged), check=True)
    print(f"Control input: {merged.stat().st_size / 1e6:.0f} MB")

    # Before anything is timed: get the third-party sources on disk once.
    print("\nDownloading Planetiler's profile sources (once, before any timing)...", flush=True)
    run_planetiler(download_sources_cmd(args.planetiler_jar, merged, work / "download-tmp"))

    results = [run_build("control", work, args.planetiler_jar, merged, union_poly, args.max_zoom)]
    for state, poly in zip(args.states, shard_polys):
        results.append(run_build(f"arm-a-{state}", work, args.planetiler_jar, merged, poly, args.max_zoom))
    for state, pbf, poly in zip(args.states, pbfs, shard_polys):
        results.append(run_build(f"arm-b-{state}", work, args.planetiler_jar, pbf, poly, args.max_zoom))

    print("\n\n=== Temp disk, measured rather than assumed ===")
    print(f"{'build':22s} {'input':>10s} {'peak (real)':>12s} {'x':>7s} {'apparent':>10s} {'x':>7s} {'minutes':>8s}")
    for r in results:
        print(
            f"{r.name:22s} {r.input_bytes / 1e9:9.2f}G {r.peak_tmp_bytes / 1e9:11.2f}G {r.disk_multiplier:6.1f}x "
            f"{r.peak_apparent_bytes / 1e9:9.2f}G {r.apparent_multiplier:6.1f}x {r.seconds / 60:8.1f}"
        )
    print(
        f"\nBASEMAP.md's table assumes 5x and treats Planetiler's 10x planet guidance as the pessimistic bound. "
        f"The control build here measured {results[0].disk_multiplier:.1f}x of real disk."
    )
    print(
        "The apparent column is what a naive walk reports. Planetiler's node map is a sparse file sized by the\n"
        "node-ID space, so apparent size barely moves with the input and any multiplier taken from it is fiction -\n"
        "which is what the first run of this spike reported before st_blocks replaced st_size."
    )
    print("\nNow compare. Arm A isolates the ranking question; arm B adds padding:\n")
    for arm in ("a", "b"):
        shards = " ".join(f"--shard {work / f'arm-{arm}-{s}'}" for s in args.states)
        print(f"  python compare_shards.py --control {work / 'control'} {shards} --seam {seam_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--states", nargs="+", default=list(DEFAULT_STATES), help="Adjacent Geofabrik state names (default: %(default)s)"
    )
    parser.add_argument("--planetiler-jar", type=Path, required=True, help="Path to planetiler.jar")
    parser.add_argument(
        "--mode",
        choices=("seam", "disk", "determinism"),
        default="seam",
        help="seam: control + both arms. disk: one build per region, fitted. determinism: the same input built twice, "
        "which is the noise floor every other number rests on. Default: %(default)s",
    )
    parser.add_argument(
        "--geofabrik-base",
        default=GEOFABRIK_BASE,
        help="Where the extracts live. States sit under .../north-america/us; regions like us-northeast one level up.",
    )
    parser.add_argument("--max-zoom", type=int, default=14, help="Tile pyramid depth (default: %(default)s)")
    parser.add_argument("--work-dir", type=Path, default=WORK_DIR, help="Where builds land (default: %(default)s)")
    main(parser.parse_args())
