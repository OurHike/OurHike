"""Change-aware sync of Export's artifacts to Cloudflare R2 (S3-compatible).

See TECHNICAL_ARCHITECTURE.md's "Publish, change-aware end to end" section
and pipeline/README.md. The chunking/hashing-granularity question that
section flags is already resolved (ROADMAP.md Phase 2: "whole corridor, one
package") - this module doesn't need to revisit it, just diff whatever
per-artifact manifests Export already produces (export_trails.py's
trails_manifest.json, export_poi.py's poi/manifest.json, export_elevation.py's
elevation_manifest.json) plus export_pmtiles.py's per-tier background
archives (see BACKGROUND_ARCHIVES), which don't get their own manifest - this
module hashes those directly rather than silently skipping the two largest
artifacts in the whole pipeline.

Core rule: only upload an artifact whose hash actually changed, and never
write a new `latest.json` version if nothing changed - not even a no-op
bump. One SHA256 per artifact, never one combined hash for everything (per
TECHNICAL_ARCHITECTURE.md's explicit "per-artifact, not one hash for
everything" - the same reasoning `export_pmtiles.py`/`export_trails.py`/
`export_poi.py` already apply per-artifact rather than per-run).

R2 credentials/endpoint are read from the environment only (R2_ENDPOINT_URL,
R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY) - never hardcoded, same
discipline backend/app/config.py already applies to Supabase credentials.

Writes are disabled by default. A trusted environment must explicitly opt in by
setting R2_WRITE_ENABLED=true before publish.py is allowed to upload anything.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

import boto3

ROOT = Path(__file__).parent
PROCESSED_DIR = ROOT / "data" / "processed"
MANIFEST_KEY = "latest.json"
WRITE_ENABLED_ENV_VAR = "R2_WRITE_ENABLED"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# One background raster archive per download tier the client offers.
#
# The Downloads screen (client/src/lib/downloadDetail.ts) lets a hiker pick
# Light / Standard / Fine, and each is a separate PMTiles archive built at a
# different max zoom by export_pmtiles.py:
#
#     light     z6-11    ~64 MB    export_pmtiles.py --max-zoom 11 --out ...
#     standard  z6-12    ~314 MB   export_pmtiles.py                (default)
#     fine      z6-13    ~1.18 GB  export_pmtiles.py --max-zoom 13 --out ...
#
# Written as a named mapping rather than a hardcoded tuple of filenames so
# that a tier the app offers but the pipeline cannot produce is a failing
# test rather than a download that 404s on a mountain. That was a real gap:
# background_z11.pmtiles did not exist while the app was already offering
# Light.
BACKGROUND_ARCHIVES = {
    "light": "background_z11.pmtiles",
    "standard": "background.pmtiles",
    "fine": "background_z13.pmtiles",
}


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
SIDECARS = ("build_state.json",)


def collect_sidecars() -> dict[str, dict]:
    """Build metadata to upload beside a new version. See SIDECARS."""
    found: dict[str, dict] = {}
    for name in SIDECARS:
        path = PROCESSED_DIR / name
        if path.exists():
            found[name] = {"path": str(path), "sha256": sha256_file(path)}
    return found


def collect_artifacts() -> dict[str, dict]:
    """Gather every publishable artifact into one flat {name: {path, sha256}}
    dict, reading whichever of Export's manifests actually exist (a fresh
    checkout that's only run some export scripts still publishes what it
    has) plus the raster background, hashed directly since export_pmtiles.py
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

    for name in BACKGROUND_ARCHIVES.values():
        path = PROCESSED_DIR / name
        if path.exists():
            artifacts[name] = {"path": str(path), "sha256": sha256_file(path)}

    return artifacts


def _load_remote_manifest(s3_client, bucket: str) -> dict | None:
    try:
        body = s3_client.get_object(Bucket=bucket, Key=MANIFEST_KEY)["Body"].read()
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


def publish(
    artifacts: dict[str, dict] | None = None,
    *,
    sidecars: dict[str, dict] | None = None,
    s3_client=None,
    bucket: str | None = None,
) -> dict:
    """Diff `artifacts` (defaults to collect_artifacts()'s real output)
    against the bucket's current latest.json, upload only what changed, and
    write a new manifest version only if at least one artifact actually
    changed. Returns a summary dict - uploaded/skipped artifact names,
    whether a new version was written, and the resulting version id.

    `sidecars` (build metadata, see SIDECARS) never affects that decision and
    is uploaded only when a version is written."""
    if not writes_enabled():
        raise PermissionError(f"R2 writes are disabled. Set {WRITE_ENABLED_ENV_VAR}=true before publishing.")

    if artifacts is None:
        artifacts = collect_artifacts()
    if sidecars is None:
        sidecars = collect_sidecars()

    if s3_client is None:
        s3_client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        )
    if bucket is None:
        bucket = os.environ["R2_BUCKET"]

    remote_manifest = _load_remote_manifest(s3_client, bucket)
    remote_artifacts = remote_manifest["artifacts"] if remote_manifest else {}

    uploaded: list[str] = []
    skipped: list[str] = []
    for name, entry in artifacts.items():
        remote_entry = remote_artifacts.get(name)
        if remote_entry is not None and remote_entry["sha256"] == entry["sha256"]:
            skipped.append(name)
            continue
        s3_client.upload_file(entry["path"], bucket, name)
        uploaded.append(name)

    if not uploaded:
        return {
            "uploaded": [],
            "skipped": sorted(skipped),
            "sidecars": [],
            "version_written": False,
            "version": remote_manifest["version"] if remote_manifest else None,
        }

    new_version = str(uuid.uuid4())

    # After the decision, never before: a sidecar must never be able to cause
    # a version, and must never describe data that was not published.
    for name, entry in sidecars.items():
        s3_client.upload_file(entry["path"], bucket, name)

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
            **{name: {"sha256": entry["sha256"]} for name, entry in artifacts.items()},
        },
    }
    # Recorded so a reader can tell whether the live state describes this
    # version's bytes, but kept out of "artifacts" so nothing downstream can
    # mistake build metadata for something a hiker downloads.
    if sidecars:
        new_manifest["sidecars"] = {name: {"sha256": entry["sha256"]} for name, entry in sidecars.items()}
    s3_client.put_object(Bucket=bucket, Key=MANIFEST_KEY, Body=json.dumps(new_manifest, indent=2).encode("utf-8"))

    return {
        "uploaded": sorted(uploaded),
        "skipped": sorted(skipped),
        "sidecars": sorted(sidecars),
        "version_written": True,
        "version": new_version,
    }


def main() -> dict:
    artifacts = collect_artifacts()
    if not artifacts:
        print("No exported artifacts found under data/processed/ - run the export scripts first.")
        return {"uploaded": [], "skipped": [], "version_written": False, "version": None}

    result = publish(artifacts)
    if result["version_written"]:
        print(f"Published version {result['version']}: uploaded {result['uploaded']}, skipped {result['skipped']}.")
        if result["sidecars"]:
            print(f"Build metadata published alongside it: {result['sidecars']}.")
    else:
        print(f"Nothing changed - all {len(result['skipped'])} artifacts already up to date. No new version written.")
    return result


if __name__ == "__main__":
    try:
        main()
    except PermissionError as exc:
        print(exc)
        raise SystemExit(1)
