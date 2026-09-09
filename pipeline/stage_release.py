"""Stage a candidate release folder, without changing what any hiker gets.

The `stage` job of DATA_RELEASES.md section 2 (#1314). It writes
`releases/<id>/` and appends `releases/index.json`; it does not touch
`latest.json`, and that single omission is the whole design. `latest.json` is
the only object that decides which bytes a phone resolves, so a job that never
writes it cannot change anybody's map however wrong it is - which is what lets
this run weekly, unattended, against a bucket real people download from.

WHY NOT publish.py. That module does the same shape of work and cannot be
reused for it, for two reasons rather than one:

  - It has no CLI at all. `main()` takes no arguments and every decision comes
    from the environment, because it has exactly one caller shape.
  - `_stage_release`'s `CopySource` is the FLAT key - the artifact this run
    just uploaded to the bucket root. That is right for a publish, which is
    making those flat keys current. It is wrong here: staging must copy
    forward from `releases/<previous>/`, and must not write a flat key at all.

WHAT COPY-FORWARD BUYS, and why every folder is still complete. An artifact
whose sha256 matches the previous release is `copy_object`'d across, server
side, so a 1.6 GB release costs one copy per unchanged artifact and no
transfer. Only genuinely new bytes are uploaded. But the folder that results
holds EVERYTHING, not a delta - a hiker's client resolves exactly one folder
and must find it all there, and a folder holding only the week's changes would
make correctness depend on chasing a chain backwards. One gap in that chain is
a 404 on a mountain.

PROVENANCE IS CHASED, NOT RESTATED. Each artifact records the release its
bytes actually originated in, taken from the previous manifest's own answer
rather than set to the previous release id. An artifact unchanged for six
weeks says so, instead of six folders each claiming to be where it came from.

THE MANIFEST LANDS LAST, and the keys are validated before the first write.
Both are `_stage_release`'s properties and both are kept: a manifest written
early describes bytes that may not arrive, and a name that breaks the layout
must fail the run rather than leave half a folder behind.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

import publish
from lib import data_env, releases
from lib.manifest_paths import from_manifest_path
from lib.r2_keys import assert_valid_keys


def previous_manifest(s3_client, bucket: str, environment: str, index: dict | None) -> tuple[str | None, dict]:
    """The most recent release's id and manifest, or (None, {}) if there is none.

    A missing manifest under a listed id is treated as no previous release
    rather than as an error, and that is deliberate: it means the index knows
    about a folder whose contents nobody can describe, so nothing in it is
    safe to copy forward. Staging everything fresh is the honest response -
    expensive, and correct.
    """
    ids = releases.index_ids(index)
    if not ids:
        return None, {}
    previous = ids[-1]
    key = data_env.scope_key(environment, releases.release_key(previous, releases.RELEASE_MANIFEST_NAME))
    manifest = publish.load_remote_json(s3_client, bucket, key)
    if not isinstance(manifest, dict):
        print(f"Release {previous} lists no readable manifest; staging every artifact fresh.", file=sys.stderr)
        return None, {}
    return previous, manifest


def origin_of(name: str, previous_id: str, previous_manifest_entry: dict | None) -> str:
    """Which release these bytes actually came from.

    Chased through the previous manifest rather than assumed to be the
    previous release, so an artifact untouched for six weeks names the week it
    was built in and not the week it was last copied.
    """
    if isinstance(previous_manifest_entry, dict):
        recorded = previous_manifest_entry.get("origin")
        if isinstance(recorded, str) and recorded:
            return recorded
    return previous_id


def plan_stage(artifacts: dict[str, dict], previous_id: str | None, previous: dict) -> dict[str, dict]:
    """What each artifact needs: a copy from the previous folder, or an upload.

    Pure, so the decision is testable without a bucket. Returns one entry per
    artifact with its `action`, `sha256`, `origin` and (for uploads) `path`.
    """
    prior = previous.get("artifacts", {}) if isinstance(previous.get("artifacts"), dict) else {}
    planned = {}
    for name, entry in sorted(artifacts.items()):
        before = prior.get(name)
        unchanged = previous_id is not None and isinstance(before, dict) and before.get("sha256") == entry["sha256"]
        planned[name] = {
            "action": "copy" if unchanged else "upload",
            "sha256": entry["sha256"],
            "origin": origin_of(name, previous_id, before) if unchanged else None,
            "path": entry.get("path"),
        }
    return planned


def stage(
    release_id: str,
    *,
    s3_client=None,
    bucket: str | None = None,
    environment: str | None = None,
    artifacts: dict[str, dict] | None = None,
    sidecars: dict[str, dict] | None = None,
) -> dict:
    """Write `releases/<release_id>/` and append the index. Never writes latest.json."""
    environment = data_env.resolve(environment)

    if not publish.writes_enabled():
        raise PermissionError(f"R2 writes are disabled. Set {publish.WRITE_ENABLED_ENV_VAR}=true before staging a release.")

    if artifacts is None:
        artifacts = publish.collect_artifacts()
    if sidecars is None:
        sidecars = publish.collect_sidecars()

    # `conditions/` is excluded here exactly as it is from a publish's release
    # folder: safety data is rewritten in place on an hourly clock, and an
    # immutable folder cannot express a closure that has reopened.
    stageable = {name: entry for name, entry in {**artifacts, **sidecars}.items() if releases.is_release_artifact(name)}

    # The gap between an exporter recording a hash and this reading the file is
    # where a stale artifact gets published with a manifest that vouches for
    # bytes it no longer has. publish.verify_hashes closes it for a publish;
    # a release folder is the copy people roll BACK to, so it matters more here.
    publish.verify_hashes(stageable)

    if s3_client is None:
        s3_client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        )
    if bucket is None:
        bucket = os.environ["R2_BUCKET"]

    index_key = data_env.scope_key(environment, releases.RELEASE_INDEX_KEY)
    index = publish.load_remote_json(s3_client, bucket, index_key)

    if release_id in releases.index_ids(index):
        raise ValueError(
            f"{release_id} is already in the release index. Release folders are written once and never "
            "overwritten - pick the next id rather than restaging over one somebody may be reading."
        )

    previous_id, previous = previous_manifest(s3_client, bucket, environment, index)
    planned = plan_stage(stageable, previous_id, previous)

    # Every key, including the manifest's, before the first write.
    assert_valid_keys(
        [
            index_key,
            *(
                data_env.scope_key(environment, releases.release_key(release_id, name))
                for name in [*planned, releases.RELEASE_MANIFEST_NAME]
            ),
        ]
    )

    manifest_artifacts = {}
    for name, step in planned.items():
        destination = data_env.scope_key(environment, releases.release_key(release_id, name))
        if step["action"] == "copy":
            source = data_env.scope_key(environment, releases.release_key(step["origin"], name))
            s3_client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": source}, Key=destination)
            origin = step["origin"]
        else:
            path, extra = publish.upload_args(name, from_manifest_path(step["path"]))
            s3_client.upload_file(path, bucket, destination, ExtraArgs=extra)
            origin = release_id
        manifest_artifacts[name] = {"sha256": step["sha256"], "origin": origin}

    # Last of the folder's contents, so it never describes bytes that have not
    # landed.
    s3_client.put_object(
        Bucket=bucket,
        Key=data_env.scope_key(environment, releases.release_key(release_id, releases.RELEASE_MANIFEST_NAME)),
        Body=json.dumps({"release": release_id, "artifacts": manifest_artifacts}, indent=2).encode("utf-8"),
    )

    # The index last of all, because it is what advertises the folder as
    # somewhere to look. `candidate` until the battery in section 3 says
    # otherwise - nothing here has checked these bytes, only written them.
    s3_client.put_object(
        Bucket=bucket,
        Key=index_key,
        Body=json.dumps(
            releases.append_release(
                index,
                release_id=release_id,
                # A staged release has no `latest.json` version - that is the
                # point of it - so the id stands in for one. The field exists
                # so a folder and the pointer that described it can be matched
                # up later; here there is nothing yet to match, and the
                # promotion that creates one is a merged pull request.
                version=release_id,
                created_at=datetime.now(timezone.utc).isoformat(),
                status=releases.STATUS_CANDIDATE,
            ),
            indent=2,
        ).encode("utf-8"),
    )

    copied = sorted(name for name, step in planned.items() if step["action"] == "copy")
    uploaded = sorted(name for name, step in planned.items() if step["action"] == "upload")
    return {
        "release_id": release_id,
        "previous_release": previous_id,
        "copied": copied,
        "uploaded": uploaded,
        "environment": environment,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--release-id", required=True, help="The folder to write, from plan_release.py.")
    parser.add_argument("--json", metavar="OUT", type=Path, help="Write the staging report to OUT.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = stage(args.release_id)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2))

    print(f"Staged releases/{report['release_id']}/ in {report['environment']}:")
    print(f"  uploaded {len(report['uploaded'])}, copied forward {len(report['copied'])}")
    if report["previous_release"]:
        print(f"  copy-forward source: {report['previous_release']}")
    print("  latest.json untouched - this release is a candidate, not a promotion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
