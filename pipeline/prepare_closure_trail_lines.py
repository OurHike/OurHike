"""prepare_closure_trail_lines: a release's trail lines, read once per release, for the hourly cut of area closures.

    OURHIKE_DATA_ENV=ua DATA_BASE_URL=https://data.ourhike.org python prepare_closure_trail_lines.py \
        [--out-dir data/raw/closure_trail_lines] [--reuse-dir data/raw/weather/release]
    python prepare_closure_trail_lines.py --release-output "$GITHUB_OUTPUT"      # the current release's id, only
    python prepare_closure_trail_lines.py --from-file <nearby_trails.geojson> [--at-file <trails.geojson>] \
        --release <id> [--out-dir DIR]

WHAT IT IS FOR. Decision 187 (S6, the maintainer's poll of 2026-10-11), building
#1152 — Move OPRHP's temporary closures onto the conditions clock, where a
safety layer belongs — for every club closure: an area closure's trails are
crossed out where they run inside it, cut by the hourly build as NYS Parks'
areas already are monthly (int_trail_lines__network_area_closures). The cut is
SQL (int_closures__area_trail_cuts). What the hourly lane lacks is the lines:
it builds the closures and warnings marts from the conditions extract and
never the trail network, which only the monthly lane builds. This file is
where the lines come from.

THE INPUT IS EVERY TRAIL LINE THE PHONE DRAWS, from the environment's current
release (SOURCE_KEYS): its nearby_trails.geojson, the layer a phone draws every
nearby trail from (nearby_trails.pmtiles is cut from it, pub_nearby_trails.sql
says so), and its trails.geojson, the A.T.'s own centerline chains, side
trails and spurs, which a phone draws the A.T. from
(client/src/lib/config.ts's TRAILS_KEY). So a crossed-out stretch is cut from
the very line the phone draws under it.

THE A.T. IS CUT LIKE ANY TRAIL (decision 192, the maintainer's poll of
2026-10-14, "Yes, like any trail"; the recommendation had been that only ATC
closes the A.T.): decision 187's "an area's trails are crossed out where they
run inside it" includes the A.T., and the sheet names the closing
organisation. Until then this read nearby_trails.geojson alone, which does not
carry the A.T.'s lines, so no club's area ever crossed the A.T. out. One place
is affected: OPRHP's undated 2023 "Area Closed - No Entry" areas at Bear
Mountain. The decision was shown 1.8 A.T. miles there (ATC's ANST_Centerline
against UA's notices.json, whose areas are grown 100 m); against the areas as
OPRHP drew them, which is what the cut reads, the A.T. runs along their edges
rather than through them, and what lies inside is three pieces of centerline,
18.5, 51.2 and 11.7 m long, and 996 m of A.T. side trails, 1.62 centerline
miles lying within 25 m of an edge (Measured 2026-10-14 on release
2026-10-10-2's trails.geojson and OPRHP's layer read live that evening; ATC's
centerline gives 0.07 miles inside, the release's 0.05). The monthly
vector cut (int_trail_lines__network_area_closures) still leaves the A.T.
alone, because it splits only the nearby network's lines, and it is left so:
this hourly mark is drawn over the A.T.'s own line on the phone
(client/src/map/style.ts puts every club closure above it), which is what the
decision is about.

MEASURED 2026-10-11 on UA's release 2026-10-10-2, in a 4-core sandbox other
builds shared: nearby_trails.geojson is 539,755,093 bytes and 141,369,506
gzipped, as latest.json lists it, and downloaded in 11.08 s; it holds 364,668
lines with 18,000,076 vertices, each `id` unique. DuckDB 1.5.5's spatial
ST_Read read it in 63.7 s at a load average near 2, peaking at 1,752 MiB of
resident memory, and this script, as it then wrote the file, took 130.6 s and
peaked at 2,264 MiB at a load average of 14 to 23 on the sandbox's 4 cores,
writing 364,167 lines and 17,836,683 vertices in 85,588,154 bytes. The same
release's trails.geojson is 6,035,859 bytes and 1,620,827 gzipped, 1,659 lines
(463 centerline chains and 1,196 side trails), each `id` unique within it
(Measured 2026-10-14); whether any is also an `id` of the nearby file's has
not been checked, and prepare() keeps one row per id either way. A quiet runner
should take less; its log line settles by how much. A release changes about
once a day on UA: 8 releases between 2026-10-02 and 2026-10-10
(releases/index.json, read 2026-10-11).

RUN ONCE PER RELEASE, AND NOT IN THE CLOSURES JOB. publish-weather.yml's
build job runs it beside build_weather_squares.py, which already downloads
both files when UA's release moves (its LINE_KEYS), and caches its answer
under the release's id for publish-conditions.yml to restore, as the weather
squares are. That job's own header says why a 141 MB download does not belong
inside the closures job: "putting that inside the closures job is putting a
new way to be slow in front of the safety data", whose publish job's caps
already add to 899 of its 900 seconds
(.github/tests/test_conditions_build_budget.py). --reuse-dir takes the squares
step's copy of each file when its sha256 is the one latest.json lists, so a
release is downloaded once. --release-output writes the release's id first,
so the weather job looks its cache up by that id and runs this only when no
entry holds it.

THE CACHE KEY CARRIES SCHEMA (publish-weather.yml and publish-conditions.yml,
`closure-trail-lines-v<SCHEMA>-`), and SCHEMA moves whenever what a prepared
file holds changes, so the conditions job can never restore a file written to
an older rule: SCHEMA 1's held no A.T. line. RELEASE_FILE carries it too, and
`prepared()` refuses a directory of any other.

NOTHING IS EVER HALF-WRITTEN. LINES_FILE is written beside itself and renamed
into place, then RELEASE_FILE, which names the release LINES_FILE holds, so
an interrupted run leaves the last release's pair whole. A release this
already holds is not read again (RELEASE_FILE matches), and an environment
whose latest.json names no release (production's, read 2026-10-11) has
nothing to prepare: this says so and leaves the directory as it is.

--from-file (and --at-file) prepares local GeoJSON with no request: the
fixture build's lines (step_closure_trail_lines.py --geojson), and a hand run
over downloaded files.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import duckdb

from lib import data_env
from lib.atomic_write import write_text_atomically
from lib.hashing import sha256_file
from lib.http_retry import download_with_retry, request_with_retry
from lib.r2_keys import RELEASE_ID_PATTERN
from lib.user_agent import USER_AGENT

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "data" / "raw" / "closure_trail_lines"
#: build_weather_squares.py's RELEASE_DIR, where that script leaves the release's line files. Written out rather than
#: imported: that module imports rasterio and numpy for the half of its job this file does not do.
REUSE_DIR = ROOT / "data" / "raw" / "weather" / "release"
#: The nearby trail lines' release artifact, by its key in latest.json.
NEARBY_KEY = "nearby_trails.geojson"
#: The A.T.'s own lines' release artifact (decision 192).
AT_KEY = "trails.geojson"
#: Every release artifact this reads: every trail line a phone draws.
SOURCE_KEYS = (NEARBY_KEY, AT_KEY)
LINES_FILE = "lines.parquet"
RELEASE_FILE = "release.json"
#: RELEASE_FILE's schema, and what a prepared file holds: a reader refuses one it does not know rather than guessing at
#: its fields, and the cache key carries it (the docstring's "THE CACHE KEY CARRIES SCHEMA"). 1: nearby_trails.geojson
#: alone. 2: trails.geojson's lines too (decision 192).
SCHEMA = 2
#: The phone file's grid, 5 decimal places (pub_conditions_notices' header), which every line is rounded to here.
PRECISION = 0.00001
#: prepare()'s docstring has the sizes this was picked from.
ZSTD_LEVEL = 9


def prepared(out_dir: Path) -> dict | None:
    """RELEASE_FILE's document, when it and LINES_FILE are both there and the schema is this one's; otherwise None."""
    try:
        document = json.loads((out_dir / RELEASE_FILE).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if document.get("schema") != SCHEMA or not (out_dir / LINES_FILE).exists():
        return None
    return document


def prepare(
    sources: dict[str, Path],
    out_dir: Path,
    *,
    release: str,
    environment: str | None,
    source_sha256s: dict[str, str | None] | None,
) -> dict:
    """Write the lines of every file in `sources` (a release key, such as NEARBY_KEY, to its GeoJSON on disk) to
    out_dir as LINES_FILE, then RELEASE_FILE naming `release`. Returns RELEASE_FILE's document.

    One row per LineString or MultiLineString feature: `release`, `line_id` (the feature's `id`), its bounding box
    (`xmin`, `ymin`, `xmax`, `ymax`), `geometry`, its GeoJSON text at PRECISION, the grid the phone file is cut to
    (pub_conditions_notices rounds every geometry there with ST_ReducePrecision, as this does), and `source`, the key of
    the file it came from. Rounding moves a vertex by at most 0.78 m (macros/notice_phone_geometry.sql has the
    arithmetic), and a line under about a metre long collapses and is left out: 501 of UA's 364,668 nearby lines did
    (Measured 2026-10-11), none of them a stretch anybody could see crossed out. A feature with no geometry, or one
    that is not a line, is not a trail anything can be cut from, and is left out too. ONE ROW PER `line_id`, which
    stg_derived__closure_trail_lines keys on and whose source test holds rows sharing a key to exact copies, across
    the files as within one: a feature with no `id` is named by its geometry's hash, two lines that share an `id` are
    each told apart by their own geometry's hash, and an exact copy is written once. Every `id` is unique within each
    of UA's two files of release 2026-10-10-2 (Measured 2026-10-11 and 2026-10-14; across them it was not checked);
    the rule is here so that a release where one is not cannot fail the hourly build, which a failed test there would
    stop whole.

    ORDERED BY PLACE, west to east, and compressed hard, because the file is cached once a release and restored by every
    hourly run: neighbouring lines share the leading digits of their coordinates. Measured 2026-10-11 on the nearby
    file: 85,588,154 bytes at zstd level 9 in 23.8 s, against 119,483,826 at the default level in line-id order and
    163,557,313 at the release's own 6 decimal places.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    part = out_dir / f"{LINES_FILE}.part"
    keys = sorted(sources)
    read = "\n                union all\n".join(
        f"""
                select
                    cast(? as varchar) as source,
                    coalesce(cast(id as varchar), 'geometry:' || md5(st_astext(geom))) as feature_id,
                    st_reduceprecision(geom, {PRECISION}) as geom
                from st_read(?)
                where geom is not null and st_dimension(geom) = 1"""
        for _ in keys
    )
    con = duckdb.connect()
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute(
            f"""
            create table lines as
            with features as ({read}
            ),

            kept as (
                select feature_id, geom, min(source) as source from features
                where geom is not null and not st_isempty(geom) and st_dimension(geom) = 1
                group by feature_id, geom
            )

            select
                case
                    when count(*) over (partition by feature_id) = 1 then feature_id
                    else feature_id || '#' || md5(st_astext(geom))
                end as line_id,
                source,
                geom
            from kept
            """,
            [value for key in keys for value in (key, str(sources[key]))],
        )
        counted = {
            source: (lines, vertices)
            for source, lines, vertices in con.execute(
                "select source, count(*), coalesce(sum(st_npoints(geom)), 0) from lines group by source"
            ).fetchall()
        }
        con.execute(
            f"""
            copy (
                select
                    cast(? as varchar) as release,
                    line_id,
                    st_xmin(geom) as xmin,
                    st_ymin(geom) as ymin,
                    st_xmax(geom) as xmax,
                    st_ymax(geom) as ymax,
                    cast(st_asgeojson(geom) as varchar) as geometry,
                    source
                from lines
                order by xmin, ymin, line_id
            ) to '{part}' (format parquet, compression zstd, compression_level {ZSTD_LEVEL})
            """,
            [release],
        )
    finally:
        con.close()
    os.replace(part, out_dir / LINES_FILE)
    sha256s = source_sha256s or {}
    document = {
        "schema": SCHEMA,
        "environment": environment,
        "release": release,
        "sources": {key: {"sha256": sha256s.get(key), "lines": counted.get(key, (0, 0))[0]} for key in keys},
        "lines": sum(lines for lines, _ in counted.values()),
        "vertices": sum(vertices for _, vertices in counted.values()),
    }
    write_text_atomically(out_dir / RELEASE_FILE, json.dumps(document, indent=2, sort_keys=True) + "\n")
    return document


def _reusable(reuse_dir: Path | None, key: str, sha256: str) -> Path | None:
    """The squares step's copy of `key`, when it is the bytes latest.json lists."""
    if reuse_dir is None:
        return None
    candidate = reuse_dir / key
    if candidate.exists() and sha256_file(candidate) == sha256:
        return candidate
    return None


def fetch(base: str, latest: dict, key: str, scratch: Path, reuse_dir: Path | None) -> Path:
    """The release's `key` on disk: the squares step's copy when it is the same bytes, else a download, which is
    refused when its sha256 is not the one latest.json lists (a release folder is written once, so a mismatch is a
    torn download or a manifest that does not describe it)."""
    entry = latest["artifacts"][key]
    if (reused := _reusable(reuse_dir, key, entry["sha256"])) is not None:
        print(f"{key}: the copy in {reuse_dir} is release {latest['release']}'s, so nothing was downloaded")
        return reused
    dest = scratch / key
    download_with_retry(f"{base}/releases/{latest['release']}/{key}", dest, label=key, headers={"User-Agent": USER_AGENT})
    if (digest := sha256_file(dest)) != entry["sha256"]:
        raise SystemExit(
            f"{key} of release {latest['release']} has sha256 {digest}, and latest.json lists {entry['sha256']}: "
            "nothing was prepared, and the last release's lines stand"
        )
    return dest


def current_release(latest: dict) -> str | None:
    """The release latest.json names, when it carries every one of SOURCE_KEYS; None when it names none (production's,
    2026-10-11), or one without them.

    Refused unless it is a release id as lib/r2_keys.py spells one, since it goes into a cache key and a step output."""
    release = latest.get("release")
    artifacts = latest.get("artifacts") or {}
    if not release or any(key not in artifacts for key in SOURCE_KEYS):
        return None
    if not RELEASE_ID_PATTERN.match(str(release)):
        raise SystemExit(f"latest.json names release {release!r}, which is not a release id (YYYY-MM-DD, or -N after it)")
    return str(release)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--base", help="data base URL; defaults to $DATA_BASE_URL")
    parser.add_argument("--env", help="data environment to read; defaults to $OURHIKE_DATA_ENV")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR, help=f"where {LINES_FILE} and {RELEASE_FILE} go")
    parser.add_argument(
        "--reuse-dir", type=Path, help="a directory that may hold the release's line files already (the squares step's)"
    )
    parser.add_argument(
        "--release-output",
        type=Path,
        metavar="FILE",
        help="append `release=<id>` for the environment's current release (empty when it has none) to FILE, a step's "
        "$GITHUB_OUTPUT, and prepare nothing",
    )
    parser.add_argument("--from-file", type=Path, help=f"prepare this local {NEARBY_KEY}, with no request")
    parser.add_argument("--at-file", type=Path, help=f"with --from-file: the local {AT_KEY} to prepare beside it")
    parser.add_argument("--release", help="with --from-file: the release the files are from")
    args = parser.parse_args(argv)

    if args.from_file is not None:
        if not args.release:
            parser.error("--from-file needs --release")
        sources = {NEARBY_KEY: args.from_file}
        if args.at_file is not None:
            sources[AT_KEY] = args.at_file
        document = prepare(sources, args.out_dir, release=args.release, environment=args.env, source_sha256s=None)
        print(
            f"{args.out_dir / LINES_FILE}: {document['lines']:,} lines of {', '.join(map(str, sources.values()))}, "
            f"as release {args.release}"
        )
        return 0
    if args.at_file is not None:
        parser.error("--at-file needs --from-file")

    env = data_env.resolve(args.env)
    base = data_env.resolve_base(args.base, env)
    if not base:
        raise SystemExit("No data base URL: pass --base or set DATA_BASE_URL.")
    latest = request_with_retry(f"{base}/latest.json", label="latest.json", headers={"User-Agent": USER_AGENT}).json()
    release = current_release(latest)
    if args.release_output is not None:
        with args.release_output.open("a", encoding="utf-8") as out:
            out.write(f"release={release or ''}\n")
        print(f"{env}'s current release is {release or 'none'}.")
        return 0
    if release is None:
        print(f"{env}'s latest.json names no release carrying {' and '.join(SOURCE_KEYS)}, so there is nothing to prepare.")
        return 0
    sha256s = {key: latest["artifacts"][key]["sha256"] for key in SOURCE_KEYS}
    held = prepared(args.out_dir)
    if (
        held
        and (held.get("environment"), held.get("release")) == (env, release)
        and {key: (held.get("sources") or {}).get(key, {}).get("sha256") for key in SOURCE_KEYS} == sha256s
    ):
        print(f"{env} release {release}'s trail lines are already prepared: {held['lines']:,} lines.")
        return 0

    with tempfile.TemporaryDirectory(prefix="closure-trail-lines-") as scratch:
        sources = {key: fetch(base, latest, key, Path(scratch), args.reuse_dir) for key in SOURCE_KEYS}
        document = prepare(sources, args.out_dir, release=release, environment=env, source_sha256s=sha256s)
    size = (args.out_dir / LINES_FILE).stat().st_size
    by_source = ", ".join(f"{entry['lines']:,} from {key}" for key, entry in document["sources"].items())
    print(
        f"{env} release {release}: {document['lines']:,} trail lines ({by_source}), {document['vertices']:,} vertices, "
        f"{size:,} bytes in {args.out_dir / LINES_FILE}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
