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


def publish(artifacts: dict[str, dict] | None = None, *, s3_client=None, bucket: str | None = None) -> dict:
    """Diff `artifacts` (defaults to collect_artifacts()'s real output)
    against the bucket's current latest.json, upload only what changed, and
    write a new manifest version only if at least one artifact actually
    changed. Returns a summary dict - uploaded/skipped artifact names,
    whether a new version was written, and the resulting version id."""
    if artifacts is None:
        artifacts = collect_artifacts()

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
            "version_written": False,
            "version": remote_manifest["version"] if remote_manifest else None,
        }

    new_version = str(uuid.uuid4())
    new_manifest = {
        "version": new_version,
        "artifacts": {name: {"sha256": entry["sha256"]} for name, entry in artifacts.items()},
    }
    s3_client.put_object(Bucket=bucket, Key=MANIFEST_KEY, Body=json.dumps(new_manifest, indent=2).encode("utf-8"))

    return {
        "uploaded": sorted(uploaded),
        "skipped": sorted(skipped),
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
    else:
        print(f"Nothing changed - all {len(result['skipped'])} artifacts already up to date. No new version written.")
    return result


if __name__ == "__main__":
    main()
