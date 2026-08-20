"""Change-aware sync of Export's artifacts to Cloudflare R2 (S3-compatible).

See TECHNICAL_ARCHITECTURE.md's "Publish, change-aware end to end" section
and pipeline/README.md. The chunking/hashing-granularity question that
section flags is already resolved (ROADMAP.md Phase 2: "whole corridor, one
package") - this module doesn't need to revisit it, just diff whatever
per-artifact manifests Export already produces (export_trails.py's
trails_manifest.json, export_poi.py's poi/manifest.json, export_elevation.py's
elevation_manifest.json) plus assemble_raster.py's per-tier background
archives (see BACKGROUND_ARCHIVES), which don't get their own manifest - this
module hashes those directly rather than silently skipping the two largest
artifacts in the whole pipeline.

Core rule: only upload an artifact whose hash actually changed, and never
write a new `latest.json` version if nothing changed - not even a no-op
bump. One SHA256 per artifact, never one combined hash for everything (per
TECHNICAL_ARCHITECTURE.md's explicit "per-artifact, not one hash for
everything" - the same reasoning `assemble_raster.py`/`export_trails.py`/
`export_poi.py` already apply per-artifact rather than per-run).

Where each artifact lands and what it may be called is R2_LAYOUT.md, enforced
by lib/r2_keys.py before the first upload of any run.

R2 credentials/endpoint are read from the environment only (R2_ENDPOINT_URL,
R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY) - never hardcoded, same
discipline backend/app/config.py already applies to Supabase credentials.

Writes are disabled by default. A trusted environment must explicitly opt in by
setting R2_WRITE_ENABLED=true before publish.py is allowed to upload anything.

WHICH ENVIRONMENT IS PUBLISHED TO IS ALSO NEVER A DEFAULT. This module is the
only thing in the project that writes to the bucket, which makes it the one
place an environment can be enforced rather than remembered: every key it
touches goes through lib/data_env.scope_key, so a run publishing to UA is
structurally incapable of writing production's keys rather than merely
disinclined to. OURHIKE_DATA_ENV must name one of RELEASING.md §3's three
environments; unset is an error and not production, for the reason
features/DATA_ENVIRONMENTS.md gives - the wrong guess overwrites what hikers
have already downloaded.
"""

from __future__ import annotations

import gzip
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3

from lib import data_env, releases
from lib.content_types import BINARY_TYPES, COMPRESSIBLE_TYPES
from lib.hashing import sha256_file
from lib.photo_screen import load_decisions, unpublishable_digests
from lib.photo_store import PHOTO_EXTENSION, PHOTOS_DIRNAME, photo_key
from lib.r2_keys import assert_valid_keys

ROOT = Path(__file__).parent
PROCESSED_DIR = ROOT / "data" / "processed"
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_KEY = "latest.json"

# Every manifest whose artifacts publish under `conditions/`. Named here
# rather than inline so `tests/test_publish.py` can hold it against the export
# scripts that actually write manifests - see collect_artifacts for what
# forgetting an entry costs and how quietly it costs it.
CONDITIONS_MANIFESTS = (
    "conditions_manifest.json",
    "atc_updates_manifest.json",
    "drought_manifest.json",
)
WRITE_ENABLED_ENV_VAR = "R2_WRITE_ENABLED"


# One background raster archive per download tier the client offers.
#
# The Downloads screen (client/src/lib/downloadDetail.ts) lets a hiker pick
# Light / Standard / Fine, and each is a separate PMTiles archive - since
# #191, rendered warp-once from the quads' native resolution by the
# render_cell_tiles.py fan-out and assembled into tiers by
# assemble_raster.py:
#
#     light       z0-11   background_z11.pmtiles
#     standard    z0-12   background.pmtiles
#     fine        z0-13   background_z13.pmtiles
#     quad_sheet  z0-14   quad_sheet_z14.pmtiles  (z14 within 5 mi of the
#                          trail - the optional USGS sheet of #184's
#                          vector-first plan)
#
# Sizes are recorded by the first real build's job summary, not restated
# here to drift. Written as a named mapping rather than a hardcoded tuple of
# filenames so that a tier the app offers but the pipeline cannot produce is
# a failing test rather than a download that 404s on a mountain. That was a
# real gap: background_z11.pmtiles did not exist while the app was already
# offering Light.
BACKGROUND_ARCHIVES = {
    "light": "background_z11.pmtiles",
    "standard": "background.pmtiles",
    "fine": "background_z13.pmtiles",
    "quad_sheet": "quad_sheet_z14.pmtiles",
}


# The hiking sheet's own offline archives - the primary download of #184's
# vector-first plan: the AT corridor package cut from the OpenMapTiles
# basemap (build-basemap.yml / extract_package.py) and the quantized
# terrarium DEM behind its hillshade and contours (build-dem.yml /
# export_dem.py, #186).
#
# A separate mapping from BACKGROUND_ARCHIVES on purpose: those are detail
# tiers of ONE raster sheet, chosen between by download size, where these
# are the distinct packages of the default background sheet
# (client/src/lib/packages.ts BASEMAP_PACKAGE / DEM_PACKAGE) and a hiker
# takes both. The names are load-bearing twice over: they are the flat R2
# keys the client requests, and publish()'s manifest merge is additive-only,
# so a name once published cannot be renamed by this module - it can only be
# joined by a sibling and abandoned.
OFFLINE_SHEET_ARCHIVES = {
    "basemap": "at_basemap_package.pmtiles",
    # The same corridor cut capped at z13 - the hiking sheet's Standard level
    # (#276). Its own artifact rather than a truncation the client performs,
    # because a download must be exactly the bytes its advertised size and
    # published hash describe.
    "basemap_z13": "at_basemap_package_z13.pmtiles",
    "dem": "dem.pmtiles",
}

# The sheets that get 50-mile stretch cuts (#556, cut_stretches.py). Each
# family's cut leaves `<family>_stretches_manifest.json` in PROCESSED_DIR
# and collect_artifacts() below reads it; a family added to the cutting
# workflows and not here would build stretches nothing ever publishes.
STRETCH_FAMILIES = ("at_basemap", "dem")


# Build metadata that travels with a release but is not part of it.
#
# build_state.json records every upstream freshness marker as of the fetch
# this build ran on (lib/freshness_state.capture_state). The scheduled check
# reads it back over the public URL and diffs it against live upstreams, which
# is what lets that job hold no R2 credentials at all.
#
# Deliberately NOT an artifact, for one reason that matters: an artifact's
# hash changing is what writes a new version, and this file changes whenever
# an upstream is edited - including edits that do not alter a single exported
# byte. Treated as an artifact it would bump the version for a no-op, which is
# the exact rule publish() exists to hold ("never a no-op bump").
#
# The other half of the same reasoning is why it uploads only alongside a
# version write: a state uploaded on a run that published nothing would
# describe upstreams *newer* than the data actually live in the bucket. The
# check would then compare current markers against current markers, report
# FRESH, and the map would go on serving the old data with nothing flagging
# it. That is precisely the false-fresh failure the whole check exists to
# prevent, so the state is only ever written together with the bytes it
# describes.
# Sidecar name -> the directory its builder writes it in. build_state.json
# is processed build metadata; the two photo outcome JSONs are fetch
# products, published (#465) so a cold publish machine can restore them
# over public HTTPS and skip re-downloading a photo corpus the bucket
# already holds - ~200 KB standing in for ~30 minutes of throttled
# re-fetching. Like every sidecar they never cause a version and never
# describe data that was not published.
#
# THE THREE DERIVED WATER FILES ARE HERE FOR A SHARPER REASON THAN THE PHOTO
# OUTCOMES (#812), and it is worth stating because "skip a re-fetch" undersells
# it. They were reachable only through the Actions cache: not in the
# repository, not in the bucket, present on the next runner only if a cache
# entry survived. GitHub evicts entries unread for 7 days and caps a repository
# at 10 GB against ~430 MB per run, and DATA_RELEASES.md puts releases a month
# apart - so the normal case was a miss, and run 32258156317 duly missed,
# restoring in zero seconds.
#
# What a miss costs is not time. `export_poi.read_sources()` reads whatever is
# on disk, so a run that lost them publishes a map with ~1,100 fewer crossings
# and every reachable spring gone, silently - water disappearing between
# releases, which is one of the four ways CLAUDE.md says this app can hurt
# somebody. And since #825 those rows are LIVE in the identity ledger: 1,247 of
# 4,230, or 29.5% against a MAX_RETIRE_SHARE of 20%, so the same miss now also
# trips the mass-retirement refusal and blocks the publish outright.
#
# Published here, they are restored over public HTTPS by the workflow step that
# already does this for the photo outcomes, and the cache goes back to being an
# optimisation rather than the only copy.
SIDECARS = {
    "build_state.json": "processed",
    "poi_images_atc.json": "raw",
    "poi_images.json": "raw",
    "osm_water.geojson": "raw",
    "osm_water_reach.json": "raw",
    "trail_water.json": "raw",
}


# The content-type tables live in lib/content_types.py (#845), not here.
# smoke_published.py needs COMPRESSIBLE_TYPES and verify_release.py imports
# smoke_published - and the release gate runs without boto3 on purpose, so a
# constant reached through this module stops it starting at all.

# Long enough that nothing re-fetches within a session, short enough that a
# republish reaches a phone the same day.
#
# `no-cache` for the manifest specifically, because it is the thing that says
# what the current version IS - serving a stale one would have a client verify
# fresh bytes against an old hash and reject a perfectly good download.
#
# Both are an improvement on sending no header at all rather than a tuning
# exercise: with no Cache-Control a browser applies HEURISTIC freshness from
# Last-Modified, which for an artifact published weeks ago can be days. Every
# key here is overwritten in place (DATA_RELEASES.md), so heuristic caching was
# quietly deciding how long a hiker kept stale trail data.
ARTIFACT_CACHE_CONTROL = "public, max-age=300, must-revalidate"
MANIFEST_CACHE_CONTROL = "no-cache"


def upload_args(name: str, path: str, *, compress: bool = True) -> tuple[str, dict]:
    """The path to actually upload for `name`, and its ExtraArgs.

    Returns the original path untouched for anything not in
    COMPRESSIBLE_TYPES; for the rest, a gzipped copy beside it. The copy is
    written into the same directory rather than a temp dir so it lands on
    `data/`, which is gitignored and already the shelf for derived bytes
    (CONTRIBUTING.md's "Data does not go in commits").

    `compress=False` is for the sidecars. They are build metadata on nobody's
    critical path - build_state.json is read once a day by a scheduled
    freshness job, not by a phone - so the two kilobytes are not worth putting
    a second representation of them in front of a reader. Content-Type and
    Cache-Control still apply, because those were missing for everything.
    """
    suffix = Path(name).suffix
    extra: dict[str, str] = {"CacheControl": ARTIFACT_CACHE_CONTROL}

    if suffix in BINARY_TYPES:
        extra["ContentType"] = BINARY_TYPES[suffix]
        return path, extra

    if suffix not in COMPRESSIBLE_TYPES:
        return path, extra

    extra["ContentType"] = COMPRESSIBLE_TYPES[suffix]
    if not compress:
        return path, extra

    source = Path(path)
    compressed = source.with_name(f"{source.name}.gz")
    # mtime=0 so the same input produces the same bytes on every run. The
    # object's own diffing is on the uncompressed sha256 above, so this does
    # not decide whether anything uploads - it only keeps a re-upload from
    # differing for no reason anybody can see.
    with open(source, "rb") as raw, gzip.GzipFile(compressed, "wb", 6, mtime=0) as out:
        shutil.copyfileobj(raw, out)
    extra["ContentEncoding"] = "gzip"
    return str(compressed), extra


def collect_sidecars() -> dict[str, dict]:
    """Build metadata to upload beside a new version. See SIDECARS."""
    found: dict[str, dict] = {}
    for name, shelf in SIDECARS.items():
        path = (PROCESSED_DIR if shelf == "processed" else RAW_DIR) / name
        if path.exists():
            found[name] = {"path": str(path), "sha256": sha256_file(path)}
    return found


def collect_photos() -> dict[str, str]:
    """Every cached POI photo, as {bucket key: local path}.

    Photos are not artifacts and deliberately do not go through the manifest.
    They are content-addressed (lib/photo_store.py), so the key already
    carries the checksum a manifest entry would have restated, an object's
    bytes can never change under a key, and listing several thousand of them
    in `latest.json` would add hundreds of KB to a file every client fetches
    before anything else.

    That also means they never trigger a version bump on their own, which is
    correct: a photo only becomes visible through a `poi_*.geojson` that
    references it, and that artifact's bytes changing is the real event.

    Minus what the face gate holds (#836): a flagged-undecided or refused
    photo must not reach the bucket at all, because "unreferenced" is not
    "private" - the digest that names it travels in the published outcome
    sidecars. If a held digest is somehow still referenced by an exported
    artifact (the same bytes reaching the export another way),
    verify_photo_promises() fails the publish loudly rather than letting
    this exclusion silently break a card.
    """
    photos_dir = RAW_DIR / PHOTOS_DIRNAME
    if not photos_dir.is_dir():
        return {}
    held = unpublishable_digests(RAW_DIR / "poi_images.json", load_decisions())
    if held:
        print(f"{len(held)} photo(s) held from the bucket by the face gate (#836 - review_flagged_photos.py).")
    return {photo_key(path.stem): str(path) for path in sorted(photos_dir.glob(f"*.{PHOTO_EXTENSION}")) if path.stem not in held}


def upload_photos(s3_client, bucket: str, photos: dict[str, str], prefix: str = "") -> list[str]:
    """Upload any photo the bucket does not already hold, and return what
    was uploaded - under `prefix`, which is the publishing environment's
    (lib/data_env.prefix_for).

    Existence is the whole check - no hash comparison, because the key IS
    the hash: an object already at `photos/<digest>.jpg` is by construction
    the bytes we were about to send. One cheap HEAD per photo per run beats
    both re-uploading everything and carrying a manifest of them.

    That check is per environment rather than bucket-wide, which is what makes
    a non-production environment's first publish pay for the whole corpus
    (~75 MB, features/POI_PHOTOS.md) and every later one pay for nothing. The
    duplication is deliberate: `photos/` is the one hiker-facing prefix objects
    are *deleted* from - a withdrawal is a promise made to whoever shared the
    photograph - and a shared prefix would let a withdrawal rehearsed in UA
    take the picture out of production.

    Returned unscoped, because the caller reports what was published and the
    prefix is a fact about where rather than about what.
    """
    uploaded: list[str] = []
    for key, path in photos.items():
        try:
            s3_client.head_object(Bucket=bucket, Key=f"{prefix}{key}")
            continue
        except Exception as exc:
            if "404" not in str(exc) and "NoSuchKey" not in str(exc) and "Not Found" not in str(exc):
                raise
        s3_client.upload_file(path, bucket, f"{prefix}{key}", ExtraArgs={"ContentType": "image/jpeg"})
        uploaded.append(key)
    return uploaded


def referenced_photo_keys(artifacts: dict[str, dict]) -> set[str]:
    """Every `photos/<digest>.jpg` key the exported poi_*.geojson artifacts
    reference - the promises this publish is about to make (#465). Read
    from the artifacts themselves rather than the outcome JSONs, because
    the artifact is what a hiker's card resolves against."""
    keys: set[str] = set()
    for name, entry in artifacts.items():
        if not (name.startswith("poi_") and name.endswith(".geojson")):
            continue
        document = json.loads(Path(entry["path"]).read_text(encoding="utf-8"))
        for feature in document.get("features", []):
            properties = feature.get("properties") or {}
            if properties.get("photo_key"):
                keys.add(properties["photo_key"])
            gallery = properties.get("photos")
            if gallery:
                items = json.loads(gallery) if isinstance(gallery, str) else gallery
                keys.update(item["key"] for item in items if item.get("key"))
    return keys


def verify_photo_promises(s3_client, bucket: str, prefix: str, artifacts: dict, photos: dict[str, str]) -> None:
    """Fail loudly when an exported photo_key has neither a local file nor a
    bucket object (#465).

    This is the check that let the fetches stop requiring local bytes: a
    durable outcome record vouches that a photo was obtained ONCE, and this
    is where that trust is settled against reality - by the one component
    that already holds credentials and already HEADs every photo key. A
    cleared data/ tree publishing a photo_key nobody ever uploaded used to
    be cached_photo_missing()'s job to prevent, at the cost of a ~30-minute
    re-fetch of a corpus the bucket already held.
    """
    missing: list[str] = []
    for key in sorted(referenced_photo_keys(artifacts)):
        if key in photos:
            continue  # in the local store; upload_photos settled it
        try:
            s3_client.head_object(Bucket=bucket, Key=f"{prefix}{key}")
        except Exception as exc:
            if "404" not in str(exc) and "NoSuchKey" not in str(exc) and "Not Found" not in str(exc):
                raise
            missing.append(key)
    if missing:
        shown = ", ".join(missing[:5]) + (f" (+{len(missing) - 5} more)" if len(missing) > 5 else "")
        raise RuntimeError(
            f"{len(missing)} photo key(s) referenced by the poi artifacts exist neither locally nor in the "
            f"bucket: {shown}. The outcome records promise photos nobody ever uploaded - re-run the photo "
            "fetches (delete the stale outcome JSONs first if they are wrong) before publishing."
        )


def collect_artifacts() -> dict[str, dict]:
    """Gather every publishable artifact into one flat {name: {path, sha256}}
    dict, reading whichever of Export's manifests actually exist (a fresh
    checkout that's only run some export scripts still publishes what it
    has) plus the raster background, hashed directly since assemble_raster.py
    doesn't write its own manifest."""
    artifacts: dict[str, dict] = {}

    trails_manifest = PROCESSED_DIR / "trails_manifest.json"
    if trails_manifest.exists():
        manifest = json.loads(trails_manifest.read_text())
        for kind in ("geojson", "fgb"):
            if kind in manifest:
                artifacts[f"trails.{kind}"] = {"path": manifest[kind]["path"], "sha256": manifest[kind]["sha256"]}

    poi_manifest = PROCESSED_DIR / "poi" / "manifest.json"
    if poi_manifest.exists():
        manifest = json.loads(poi_manifest.read_text())
        for poi_type, entry in manifest.items():
            for kind in ("geojson", "fgb"):
                if kind in entry:
                    artifacts[f"poi_{poi_type}.{kind}"] = {
                        "path": entry[kind]["path"],
                        "sha256": entry[kind]["sha256"],
                    }

    elevation_manifest = PROCESSED_DIR / "elevation_manifest.json"
    if elevation_manifest.exists():
        manifest = json.loads(elevation_manifest.read_text())
        artifacts["elevation_profile.json"] = {"path": manifest["path"], "sha256": manifest["sha256"]}

    # Where each blue-blazed spur leads. A real artifact rather than a sidecar
    # (unlike build_state.json): the client downloads it, and its bytes
    # changing means the map can say something different, which is exactly
    # what a version is for.
    spurs_manifest = PROCESSED_DIR / "spurs_manifest.json"
    if spurs_manifest.exists():
        manifest = json.loads(spurs_manifest.read_text())
        artifacts["spurs.json"] = {"path": manifest["path"], "sha256": manifest["sha256"]}

    # Who maintains which stretch, if export_club_sections.py has run (#594,
    # features/CORRIDOR_VIEW.md). Same shape and same reasoning as spurs.json
    # above: a small keyed artifact rather than properties on trails.geojson,
    # so it gets ordinary sha256 diffing and a run that changes no club
    # assignment uploads nothing.
    club_manifest = PROCESSED_DIR / "club_sections_manifest.json"
    if club_manifest.exists():
        manifest = json.loads(club_manifest.read_text())
        artifacts["club_sections.json"] = {"path": manifest["path"], "sha256": manifest["sha256"]}

    # The curated highlights, if export_highlights.py has run (#595,
    # features/CORRIDOR_VIEW.md). Same shape again, and the same reason a run
    # that changes nothing uploads nothing - which matters more here than for
    # its siblings, because the editorial list changes a row at a time while
    # the miles under it move whenever ATC re-surveys.
    highlights_manifest = PROCESSED_DIR / "highlights_manifest.json"
    if highlights_manifest.exists():
        manifest = json.loads(highlights_manifest.read_text())
        artifacts["highlights.json"] = {"path": manifest["path"], "sha256": manifest["sha256"]}

    # The tombstones: every POI id ever retired, so an id that has been
    # published once always resolves to something (#673,
    # features/POI_IDENTITY.md). Deliberately NOT named `poi_retired.geojson`
    # - `poi_*.geojson` is a namespace whose invariant is "live rows of one
    # poi_type", enforced by check 21 and walked by referenced_photo_keys
    # just below; export_retired_poi.py's docstring has the full reasoning.
    retired_manifest = PROCESSED_DIR / "retired_poi_manifest.json"
    if retired_manifest.exists():
        manifest = json.loads(retired_manifest.read_text())
        artifacts["retired_poi.geojson"] = {"path": manifest["path"], "sha256": manifest["sha256"]}

    # Verified closures and reports, if export_conditions.py has run
    # (features/CONDITIONS_DELIVERY.md). Ordinary artifacts rather than a
    # special case: they want the same sha256 diffing every other one gets.
    # What that diffing cannot do is make the daily bake a no-op - the baked
    # bytes carry generated_at, so their sha moves every run whether or not a
    # row changed. This comment used to promise "a day with no condition
    # changes uploads nothing and writes no new version"; that was false from
    # the day the two met (#646), and the release-staging skip below is what
    # actually keeps the daily clock from minting a release folder a day.
    #
    # Published under `conditions/` rather than at the root because the whole
    # prefix is rewritten in place on a different clock from the trail data.
    # The manifest keys its artifacts by payload name - "closures", "reports" -
    # and each becomes `conditions/<name>.json`; a manifest from before #436
    # has no "artifacts" key at all, and a KeyError here beats quietly
    # publishing a stale shape (re-running export_conditions.py rewrites it).
    # Three manifests rather than one, because three scripts produce them and
    # each runs under different conditions: export_conditions.py reads the
    # database and needs a credential that may not exist yet,
    # export_atc_updates.py reads a reviewed file in git and needs none, and
    # export_drought.py fetches a public weekly release. Sharing a manifest
    # file would make the published set depend on which ran last, since each
    # rewrites its own manifest whole, and the artifact that lost would vanish
    # from the upload with nothing said.
    #
    # THIS TUPLE IS THE THING TO EXTEND WHEN A FOURTH ARRIVES, and forgetting
    # it is silent: #720 shipped export_drought.py with its own manifest and
    # did not add the name here, so conditions/drought.json was rebuilt every
    # hour for nothing and never uploaded once. The publish log said
    # "uploaded ['conditions/atc_updates.json']" and no step failed. The test
    # beside this one now walks every *_manifest.json this directory can hold.
    for name in CONDITIONS_MANIFESTS:
        conditions_manifest = PROCESSED_DIR / name
        if conditions_manifest.exists():
            manifest = json.loads(conditions_manifest.read_text())
            for kind, entry in manifest["artifacts"].items():
                artifacts[f"conditions/{kind}.json"] = {"path": entry["path"], "sha256": entry["sha256"]}

    # The stretch units (#556): each sheet's cut writes one manifest naming
    # its context, its per-stretch archives, and the coverage index
    # (cut_stretches.py). Collected per family because the two sheets are
    # cut by different workflows on different runners - whichever ran
    # publishes what it has, the same partial-checkout posture as everything
    # above.
    for family in STRETCH_FAMILIES:
        stretches_manifest = PROCESSED_DIR / f"{family}_stretches_manifest.json"
        if stretches_manifest.exists():
            manifest = json.loads(stretches_manifest.read_text())
            for name, entry in manifest["artifacts"].items():
                artifacts[name] = {"path": entry["path"], "sha256": entry["sha256"]}

    for name in (*BACKGROUND_ARCHIVES.values(), *OFFLINE_SHEET_ARCHIVES.values()):
        path = PROCESSED_DIR / name
        if path.exists():
            artifacts[name] = {"path": str(path), "sha256": sha256_file(path)}

    # Every entry carries the byte size of the artifact as built - the
    # measurement #505 wanted published rather than hand-kept, and the thing
    # per-stretch download prompts cannot be honest without (#556: advertised
    # sizes are held to ±0.6% of measured artifacts, per unit). For the
    # gzip-uploaded text artifacts this is the DECODED size - the bytes a
    # client's fetch hands to code, the same bytes the sha256 describes.
    for entry in artifacts.values():
        entry["size_bytes"] = Path(entry["path"]).stat().st_size

    return artifacts


def _verify_hashes(entries: dict[str, dict]) -> None:
    """Every collected sha256 must describe the bytes on disk NOW, not the
    bytes the exporter had when it wrote its manifest (#659). Most entries
    carry a hash copied from an exporter's manifest file, and nothing
    between that write and this upload re-checked it - so an artifact
    rebuilt (or half-written) after its manifest was recorded would either
    upload fresh bytes under a stale hash (every hash-verifying client
    rejects the download) or skip a changed file because its stale hash
    still matches the bucket. Raises before the first upload, naming every
    mismatch, so a bad state costs a failed run instead of a poisoned
    manifest."""
    stale = {name: entry for name, entry in entries.items() if sha256_file(Path(entry["path"])) != entry["sha256"]}
    if stale:
        raise RuntimeError(
            "manifest hash does not match the file on disk for: "
            + ", ".join(sorted(stale))
            + " - the artifact changed after its exporter recorded the hash. "
            "Re-run that exporter (all the way through its gate) before publishing."
        )


def _load_remote_manifest(s3_client, bucket: str, manifest_key: str = MANIFEST_KEY) -> dict | None:
    try:
        body = s3_client.get_object(Bucket=bucket, Key=manifest_key)["Body"].read()
    except s3_client.exceptions.NoSuchKey:
        return None
    except Exception as exc:
        # boto3/moto raise a botocore ClientError (not NoSuchKey) for a
        # missing key in some code paths - treat "not found" the same way
        # regardless of which exception type carried it, re-raise anything
        # else rather than masking a real failure.
        if "NoSuchKey" not in str(exc) and "404" not in str(exc):
            raise
        return None
    return json.loads(body)


def writes_enabled() -> bool:
    """Whether this environment is explicitly allowed to publish to R2."""
    return os.environ.get(WRITE_ENABLED_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def _stage_release(
    s3_client,
    bucket: str,
    prefix: str,
    release_id: str,
    manifest: dict,
    sidecar_names: list[str],
) -> list[str]:
    """Copy this version's bytes into `releases/<id>/` and return what landed.

    SERVER-SIDE COPIES, which is what makes a complete folder affordable.
    Every artifact in the manifest is copied from its flat key - the one this
    run either just uploaded or verified unchanged - so a 1.6 GB release costs
    one `copy_object` per artifact and no second transfer. Re-uploading from
    disk would double every publish and would not even be possible for the
    artifacts this checkout did not build.

    EVERY ARTIFACT, not just the changed ones, and that is the property rather
    than an inefficiency: a hiker's client resolves one folder and must find
    everything in it (DATA_RELEASES.md section 2).

    A failed copy raises rather than warning. It means the flat key named by
    the manifest is not in the bucket, which is a real fault - and half a
    release folder is worse than none, because the index would then advertise
    something incomplete as somewhere to roll back to.
    """
    names = [name for name in sorted([*manifest["artifacts"], *sidecar_names]) if releases.is_release_artifact(name)]

    # Before the first copy, for the reason publish() validates before the
    # first upload: a name that breaks the layout must fail the run rather
    # than leave half a release folder behind. This is the one place the
    # release id itself is checked - it is the only new segment, and a folder
    # named something RELEASE_ID_PATTERN rejects would be a release nothing
    # could later resolve.
    assert_valid_keys([f"{prefix}{releases.release_key(release_id, name)}" for name in [*names, releases.RELEASE_MANIFEST_NAME]])

    staged: list[str] = []
    for name in names:
        s3_client.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": f"{prefix}{name}"},
            Key=f"{prefix}{releases.release_key(release_id, name)}",
        )
        staged.append(name)

    # The folder's own manifest, written last of the folder's contents, so it
    # never describes bytes that have not landed yet.
    s3_client.put_object(
        Bucket=bucket,
        Key=f"{prefix}{releases.release_key(release_id, releases.RELEASE_MANIFEST_NAME)}",
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
    )
    return staged


def publish(
    artifacts: dict[str, dict] | None = None,
    *,
    sidecars: dict[str, dict] | None = None,
    photos: dict[str, str] | None = None,
    s3_client=None,
    bucket: str | None = None,
    environment: str | None = None,
) -> dict:
    """Diff `artifacts` (defaults to collect_artifacts()'s real output)
    against the bucket's current latest.json, upload only what changed, and
    write a new manifest version only if at least one artifact actually
    changed. Returns a summary dict - uploaded/skipped artifact names,
    whether a new version was written, and the resulting version id.

    `sidecars` (build metadata, see SIDECARS) never affects that decision and
    is uploaded only when a version is written.

    `environment` names which of RELEASING.md §3's environments this publishes
    to, defaulting to `$OURHIKE_DATA_ENV` - which has no default of its own, so
    a caller that says nothing anywhere gets an error rather than production.
    Every key below is scoped by it exactly once, on the way out, and the
    manifest's *contents* are left unscoped: an artifact is `trails.geojson` in
    every environment, and which bytes that names is decided by the base URL
    the client was built against (client/src/lib/config.ts). That is what lets
    a manifest be read, diffed or promoted between environments without
    rewriting it."""
    if not writes_enabled():
        raise PermissionError(f"R2 writes are disabled. Set {WRITE_ENABLED_ENV_VAR}=true before publishing.")

    # Before the credentials are even read, so a run with the wrong idea of
    # where it is publishing fails while it still cannot reach the bucket.
    environment = data_env.resolve(environment)
    prefix = data_env.prefix_for(environment)

    if artifacts is None:
        artifacts = collect_artifacts()
    if sidecars is None:
        sidecars = collect_sidecars()
    if photos is None:
        photos = collect_photos()

    # Before anything is uploaded, not per-object: a name that breaks the
    # layout (pipeline/R2_LAYOUT.md) must fail the whole run rather than
    # leave half a release in the bucket under keys nobody meant to publish.
    # It also has to fail *here* rather than in review, because the manifest
    # merge below is additive-only - a key published once cannot be renamed,
    # only abandoned in place and served forever.
    #
    # Scoped first and validated after, because the key that gets checked has
    # to be the key that gets written - an environment prefix that made a legal
    # name illegal would otherwise be found by the bucket rather than by this.
    manifest_key = data_env.scope_key(environment, MANIFEST_KEY)
    assert_valid_keys(
        [
            manifest_key,
            data_env.scope_key(environment, releases.RELEASE_INDEX_KEY),
            *(f"{prefix}{name}" for name in (*artifacts, *sidecars, *photos)),
        ]
    )

    if s3_client is None:
        s3_client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        )
    if bucket is None:
        bucket = os.environ["R2_BUCKET"]

    # Re-hash every artifact and sidecar against its collected hash before
    # anything is uploaded - see _verify_hashes for why the gap between an
    # exporter's manifest and this upload cannot be trusted.
    _verify_hashes({**artifacts, **sidecars})

    remote_manifest = _load_remote_manifest(s3_client, bucket, manifest_key)
    remote_artifacts = remote_manifest["artifacts"] if remote_manifest else {}

    # Photos first, before any artifact that names them and well before the
    # manifest. A `poi_*.geojson` live in the bucket while its photos are
    # still uploading is a card pointing at a 404; the reverse - a photo
    # nothing references yet - is invisible and harmless. Ordering is the
    # only thing making that safe, since photos are outside the manifest and
    # so cannot be diffed into the same transaction as the artifacts.
    uploaded_photos = upload_photos(s3_client, bucket, photos, prefix)
    # And immediately settle every photo promise the artifacts make - the
    # loud half of #465's trust-the-record design; see verify_photo_promises.
    verify_photo_promises(s3_client, bucket, prefix, artifacts, photos)

    uploaded: list[str] = []
    skipped: list[str] = []
    for name, entry in artifacts.items():
        remote_entry = remote_artifacts.get(name)
        if remote_entry is not None and remote_entry["sha256"] == entry["sha256"]:
            skipped.append(name)
            continue
        upload_path, extra = upload_args(name, entry["path"])
        s3_client.upload_file(upload_path, bucket, f"{prefix}{name}", ExtraArgs=extra)
        uploaded.append(name)

    if not uploaded:
        return {
            "environment": environment,
            "uploaded": [],
            "skipped": sorted(skipped),
            "sidecars": [],
            "photos_uploaded": sorted(uploaded_photos),
            "version_written": False,
            "version": remote_manifest["version"] if remote_manifest else None,
        }

    new_version = str(uuid.uuid4())

    # After the decision, never before: a sidecar must never be able to cause
    # a version, and must never describe data that was not published.
    for name, entry in sidecars.items():
        upload_path, extra = upload_args(name, entry["path"], compress=False)
        s3_client.upload_file(upload_path, bucket, f"{prefix}{name}", ExtraArgs=extra)

    # Merge, don't replace: an artifact that's live in remote_artifacts but
    # wasn't produced by this run's collect_artifacts() (e.g. a checkout that
    # only re-ran export_trails.py, with no local elevation_manifest.json or
    # background pmtiles tier) must survive into the new manifest untouched -
    # the R2 object is still there, only the local checkout is partial. Local
    # entries win by name where both exist, since a freshly-collected entry
    # for a name that changed is the new source of truth; any remote name
    # with no local counterpart this run is preserved as-is.
    new_manifest = {
        "version": new_version,
        "artifacts": {
            **remote_artifacts,
            # size_bytes rides beside the hash when this run measured one
            # (#505/#556); a remote entry from before sizes were published
            # survives without one rather than gaining a guess.
            **{
                name: {"sha256": entry["sha256"], **({"size_bytes": entry["size_bytes"]} if "size_bytes" in entry else {})}
                for name, entry in artifacts.items()
            },
        },
    }
    # Recorded so a reader can tell whether the live state describes this
    # version's bytes, but kept out of "artifacts" so nothing downstream can
    # mistake build metadata for something a hiker downloads.
    if sidecars:
        new_manifest["sidecars"] = {name: {"sha256": entry["sha256"]} for name, entry in sidecars.items()}

    # A version is not automatically a release (#646). `conditions/` names
    # are excluded from release folders by design - that prefix rewrites in
    # place on a daily clock - and the baked bytes carry generated_at, so the
    # daily run's sha moves even when no row changed. Staging on such a run
    # would server-side-copy every frozen artifact into a folder
    # byte-identical to yesterday's: one duplicate folder per environment per
    # day, an index entry per day, and nothing anywhere that prunes. So a run
    # whose uploads are all excluded names freezes nothing: the pointer still
    # moves (fresh conditions hashes are the point of the bake), and it keeps
    # naming the last real release, because those are still the bytes the
    # folders hold.
    release_worthy = any(releases.is_release_artifact(name) for name in uploaded)
    if release_worthy:
        # Which folder this version's bytes are also kept in, taken from the
        # ids already used so a second publish on one day gets `-2` rather
        # than overwriting the morning's release. Read before anything under
        # `releases/` is written, because the answer decides where it is
        # written.
        index_key = data_env.scope_key(environment, releases.RELEASE_INDEX_KEY)
        release_index = _load_remote_manifest(s3_client, bucket, index_key)
        release_id = releases.next_release_id(releases.index_ids(release_index))

        # The same manifest as the pointer's, minus what may not be frozen.
        # See lib/releases.is_release_artifact: `conditions/` is rewritten in
        # place on a daily clock, and a reopened closure must stop being
        # served - which an immutable folder cannot express.
        release_manifest = {
            **new_manifest,
            "release": release_id,
            "artifacts": {name: entry for name, entry in new_manifest["artifacts"].items() if releases.is_release_artifact(name)},
        }
        staged = _stage_release(
            s3_client,
            bucket,
            prefix,
            release_id,
            release_manifest,
            sorted(sidecars),
        )

        s3_client.put_object(
            Bucket=bucket,
            Key=index_key,
            Body=json.dumps(
                releases.append_release(
                    release_index,
                    release_id=release_id,
                    version=new_version,
                    created_at=datetime.now(timezone.utc).isoformat(),
                ),
                indent=2,
            ).encode("utf-8"),
        )
    else:
        release_id = remote_manifest.get("release") if remote_manifest else None
        staged = []

    # `latest.json` LAST, after the release folder and the index it is listed
    # in, and the ordering is the same argument the photos make above: this is
    # the pointer every client fetches first, so anything it names has to
    # already be there. A reader that learns about version N and then cannot
    # find `releases/<id>/` would be looking at a release that does not exist
    # yet - which is exactly the state the rollback story assumes cannot
    # happen.
    #
    # `release` is additive rather than a replacement. Every build in the
    # field goes on reading `artifacts` from the flat keys exactly as before,
    # and this tells a reader which folder holds the same bytes - which is
    # what #374's release-over-release checks need in order to have something
    # to compare against.
    new_manifest["release"] = release_id
    s3_client.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=json.dumps(new_manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
        # Never a stale manifest. This file is what says which version is
        # current, so a cached copy would have a client verify freshly
        # downloaded bytes against a superseded hash and throw away a good
        # download. Left uncompressed too - it is 3.5 KB, and it is the one
        # object every other check reads before it can do anything.
        CacheControl=MANIFEST_CACHE_CONTROL,
    )

    return {
        "environment": environment,
        "uploaded": sorted(uploaded),
        "skipped": sorted(skipped),
        "sidecars": sorted(sidecars),
        "photos_uploaded": sorted(uploaded_photos),
        "version_written": True,
        "version": new_version,
        "release": release_id,
        "release_artifacts": staged,
    }


def main() -> dict:
    # Resolved before the artifacts are collected so that a run with no
    # environment set says so immediately, rather than after it has hashed
    # 1.6 GB of PMTiles to discover it has nowhere to put them.
    environment = data_env.resolve()

    artifacts = collect_artifacts()
    if not artifacts:
        print("No exported artifacts found under data/processed/ - run the export scripts first.")
        return {
            "environment": environment,
            "uploaded": [],
            "skipped": [],
            "photos_uploaded": [],
            "version_written": False,
            "version": None,
        }

    # Named on every run, including the ones that publish nothing. Which
    # environment a job wrote to is the fact this whole mechanism exists to
    # keep straight, and a log that omits it leaves the reader inferring it
    # from the workflow name (features/DATA_ENVIRONMENTS.md).
    where = data_env.prefix_for(environment) or "the bucket root"
    print(f"Publishing to the {environment} environment ({where}).")

    result = publish(artifacts, environment=environment)
    if result["version_written"]:
        print(f"Published version {result['version']}: uploaded {result['uploaded']}, skipped {result['skipped']}.")
        if result["sidecars"]:
            print(f"Build metadata published alongside it: {result['sidecars']}.")
    if result["photos_uploaded"]:
        # Reported whether or not a version was written: photos are outside
        # the manifest, so a run that uploads only photos legitimately writes
        # no version and would otherwise print "nothing changed".
        print(f"{len(result['photos_uploaded'])} new POI photo(s) uploaded.")

    # Both conditions, not just the photos one. This `else` used to hang off
    # the `if` above, so a run that published a version and uploaded no photos
    # printed "Published version <id>" and "Nothing changed ... No new version
    # written" one after the other. The first real publish-conditions.yml run
    # did exactly that (2026-08-08), and on a job whose whole purpose is
    # getting safety data to a hiker, a log that says it did nothing is worse
    # than a quiet one - somebody reading it concludes the bake is broken and
    # goes looking for a fault that is not there.
    if not result["version_written"] and not result["photos_uploaded"]:
        print(f"Nothing changed - all {len(result['skipped'])} artifacts already up to date. No new version written.")
    return result


if __name__ == "__main__":
    try:
        main()
    except (PermissionError, data_env.UnknownEnvironment) as exc:
        # Both are refusals to publish rather than faults, and both are worth
        # reading as a sentence: a traceback for "you did not say where" buries
        # the one line that says what to type.
        print(exc)
        raise SystemExit(1)
