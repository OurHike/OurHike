"""Each data environment's pointer: which release folder its phones read.

    python channels.py move --environment ua --release 2026-10-10-2
    python channels.py promote --to production                 # UA's current release
    python channels.py promote --to production --release 2026-09-24-2   # a rollback
    python channels.py promote --to ua --release 2026-10-03-2           # a rollback in UA

THE POINTER is `channels.json` at an environment's root, beside latest.json:
`{"<environment>": {"v1": "<release id>"}}`, one schema version per key. The
copy in the bucket is the only copy; nothing in git names the release a phone
reads any more (the maintainer, 2026-10-16). Each environment's file holds
only its own entries. The outer environment key stays, because every build
already in the field reads `document[<its environment>][<its schema version>]`
(client/src/lib/dataChannel.ts's entryIn), so a file shaped any other way
would be one those phones ignore.

THE HISTORY is `channels_history.json` beside it:
`{"environment": "<name>", "moves": [<oldest>, ..., <newest>]}`, each move
naming the release, the release it replaced, the schema version, the UTC time,
and the workflow run, commit and actor that made it. Append-only: a move
rewrites the file with the earlier moves first and unchanged, and a history
that cannot be read is refused rather than started again, because starting
again would drop every earlier record.

THREE RULES, each with a test in tests/test_channels.py:

- A pointer is moved only to a release whose manifest is already in that
  environment's own tree. A phone refuses any other and keeps its last
  release (dataChannel.ts's `resolves`), so writing one would only make the
  pointer lie. This is the check `publish.py --channels` made, kept.
- A move writes only its own environment's two keys.
- A promotion copies the release folder server side, then checks that every
  object arrived at the source's size and, where the source's ETag is a plain
  MD5, the same ETag, before it moves the pointer. A copy that does not
  verify moves nothing. The folder's manifest is copied last, so a manifest
  in the target means every object before it landed.

WHO CALLS IT. build-reference.yml's last job moves UA's pointer once every
check in that run has passed. promote-data.yml, behind the production
environment's reviewer, promotes. Nothing else: publish() never touches
either key, so no scheduled publish can move what a phone reads.

Pointer and history writes are a read, a change and a write, so their writers
share the `publish-data` concurrency group with every other writer of an
environment's root keys (.github/tests/test_publish_concurrency.py).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from functools import partial

import publish
from lib import data_env, releases
from lib.r2_keys import RELEASE_ID_PATTERN, assert_valid_keys

CHANNELS_KEY = "channels.json"
HISTORY_KEY = "channels_history.json"
DEFAULT_SCHEMA_VERSION = "v1"
SCHEMA_VERSION_PATTERN = re.compile(r"^v\d+$")


class Refused(RuntimeError):
    """A move or a promotion that would leave a phone pointed at something it cannot read. Nothing was written."""


def _not_found(exc: Exception) -> bool:
    text = str(exc)
    return "404" in text or "NoSuchKey" in text or "Not Found" in text


def _head(s3_client, bucket: str, key: str) -> dict | None:
    """The object's head, or None when it is not there. Any other failure raises."""
    try:
        return s3_client.head_object(Bucket=bucket, Key=key)
    except Exception as exc:
        if not _not_found(exc):
            raise
        return None


def _validate(environment: str, release: str, schema_version: str) -> None:
    data_env.validate(environment)
    if not SCHEMA_VERSION_PATTERN.match(schema_version):
        raise Refused(f"{schema_version!r} is not a schema version; versions are v1, v2 and so on.")
    if not isinstance(release, str) or not RELEASE_ID_PATTERN.match(release):
        raise Refused(f"{release!r} is not a release id lib/releases.next_release_id could have written.")


def manifest_key(environment: str, release: str) -> str:
    return data_env.scope_key(environment, releases.release_key(release, releases.RELEASE_MANIFEST_NAME))


def read_pointer(s3_client, bucket: str, environment: str) -> dict[str, str]:
    """`environment`'s entries in its own channels.json, `{}` when there is none.

    An entry that is not a release id is left out, as a phone leaves it out."""
    document = publish.load_remote_json(s3_client, bucket, data_env.scope_key(environment, CHANNELS_KEY))
    entries = document.get(environment) if isinstance(document, dict) else None
    if not isinstance(entries, dict):
        return {}
    return {
        version: release
        for version, release in entries.items()
        if SCHEMA_VERSION_PATTERN.match(version) and isinstance(release, str) and RELEASE_ID_PATTERN.match(release)
    }


def read_history(s3_client, bucket: str, environment: str) -> dict:
    """The history file, or an empty one when there is none. Refused when it cannot be read as one."""
    key = data_env.scope_key(environment, HISTORY_KEY)
    try:
        document = publish.load_remote_json(s3_client, bucket, key)
    except ValueError as exc:
        raise Refused(f"{key} is not JSON, so a move cannot append to it without losing what it holds.") from exc
    if document is None:
        return {"environment": environment, "moves": []}
    if (
        not isinstance(document, dict)
        or document.get("environment") != environment
        or not isinstance(document.get("moves"), list)
    ):
        raise Refused(f"{key} is not {environment}'s history, so a move cannot append to it without losing what it holds.")
    return document


def provenance_from_env(environ: dict[str, str] | None = None) -> dict[str, str | None]:
    """Who made a move, from the variables GitHub Actions sets on every run. None where a variable is unset."""
    environ = os.environ if environ is None else environ
    run_id = environ.get("GITHUB_RUN_ID") or None
    server, repository = environ.get("GITHUB_SERVER_URL"), environ.get("GITHUB_REPOSITORY")
    return {
        "workflow": environ.get("GITHUB_WORKFLOW") or None,
        "run_id": run_id,
        "run_url": f"{server}/{repository}/actions/runs/{run_id}" if run_id and server and repository else None,
        "commit": environ.get("GITHUB_SHA") or None,
        "actor": environ.get("GITHUB_ACTOR") or None,
    }


def move_pointer(
    *,
    environment: str,
    release: str,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    reason: str,
    s3_client=None,
    bucket: str | None = None,
    provenance: dict | None = None,
    now: datetime | None = None,
) -> dict:
    """Point `environment`'s `schema_version` at `release` and append the move to its history.

    Refused, before anything is written, unless `release`'s manifest is in
    `environment`'s own tree. A move to the release the pointer already names
    writes nothing and records nothing. Returns the move, with `moved` False
    for that case.
    """
    if not publish.writes_enabled():
        raise PermissionError(f"R2 writes are disabled. Set {publish.WRITE_ENABLED_ENV_VAR}=true before moving a pointer.")
    _validate(environment, release, schema_version)
    pointer_key = data_env.scope_key(environment, CHANNELS_KEY)
    history_key = data_env.scope_key(environment, HISTORY_KEY)
    assert_valid_keys([pointer_key, history_key, manifest_key(environment, release)])
    if s3_client is None:
        s3_client = publish.r2_client()
    if bucket is None:
        bucket = os.environ["R2_BUCKET"]

    if _head(s3_client, bucket, manifest_key(environment, release)) is None:
        raise Refused(
            f"{manifest_key(environment, release)} is not in the bucket, so {environment}'s phones would refuse "
            f"{release} and keep their last release. The pointer was not moved."
        )
    entries = read_pointer(s3_client, bucket, environment)
    previous = entries.get(schema_version)
    history = read_history(s3_client, bucket, environment)
    move = {
        "environment": environment,
        "schema_version": schema_version,
        "release": release,
        "previous_release": previous,
        "moved_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reason": reason,
        **(provenance if provenance is not None else provenance_from_env()),
    }
    if previous == release:
        return {**move, "moved": False}

    document = {environment: dict(sorted({**entries, schema_version: release}.items()))}
    # The pointer first, then the history: a history write that fails leaves
    # a move nobody recorded and a red run saying so, where the other order
    # could leave a record of a move that never happened.
    s3_client.put_object(
        Bucket=bucket,
        Key=pointer_key,
        Body=(json.dumps(document, indent=2) + "\n").encode("utf-8"),
        ContentType="application/json",
        CacheControl=publish.MANIFEST_CACHE_CONTROL,
    )
    history = {"environment": environment, "moves": [*history["moves"], move]}
    s3_client.put_object(
        Bucket=bucket,
        Key=history_key,
        Body=(json.dumps(history, indent=2) + "\n").encode("utf-8"),
        ContentType="application/json",
        CacheControl=publish.MANIFEST_CACHE_CONTROL,
    )
    return {**move, "moved": True}


def _list(s3_client, bucket: str, prefix: str) -> dict[str, dict]:
    """Every object under `prefix`, `{key: {"size": ..., "etag": ...}}`."""
    found: dict[str, dict] = {}
    for page in s3_client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            found[item["Key"]] = {"size": item["Size"], "etag": item.get("ETag")}
    return found


def _same(source: dict, target: dict | None) -> bool:
    """Whether a copied object is its source: the same size and, where the source's
    ETag is a plain MD5, the same ETag.

    A multipart object's ETag (`"<hash>-<parts>"`) is not a hash of its bytes,
    and a server-side copy may give the copy another one, so for those the
    size is the whole check. Reasoned from S3's documented ETag rules;
    @unvalidated against R2, which nobody here has copied a multipart object on
    and read the answer. publish.py's own artifacts are uploaded with
    upload_file, which goes multipart above boto3's 8 MB threshold, so the
    large PMTiles fall in this case. What would settle it: one promotion's log,
    which prints how many objects were checked each way."""
    if target is None:
        return False
    if target.get("ContentLength") != source["size"]:
        return False
    etag = (source.get("etag") or "").strip('"')
    if etag and "-" not in etag:
        return (target.get("ETag") or "").strip('"') == etag
    return True


def promote(
    *,
    target: str,
    release: str | None = None,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    source: str = data_env.UA,
    s3_client=None,
    bucket: str | None = None,
    provenance: dict | None = None,
    now: datetime | None = None,
) -> dict:
    """Copy `release` from `source`'s tree into `target`'s, verify it, and move `target`'s pointer to it.

    `release` defaults to the one `source`'s pointer names now. When
    `target`'s tree already holds the release's manifest (a rollback, or a
    promotion run again), nothing is copied and the folder is checked to hold
    every key its manifest lists. A promotion within one environment is a
    rollback there: the release must already be in its tree.
    """
    if not publish.writes_enabled():
        raise PermissionError(f"R2 writes are disabled. Set {publish.WRITE_ENABLED_ENV_VAR}=true before promoting.")
    data_env.validate(source)
    data_env.validate(target)
    if s3_client is None:
        s3_client = publish.r2_client()
    if bucket is None:
        bucket = os.environ["R2_BUCKET"]
    if release is None:
        release = read_pointer(s3_client, bucket, source).get(schema_version)
        if release is None:
            raise Refused(f"{source}'s pointer names no {schema_version} release, so there is nothing to promote.")
    _validate(target, release, schema_version)

    folder = data_env.scope_key(source, releases.release_key(release, ""))
    target_folder = data_env.scope_key(target, releases.release_key(release, ""))
    copied, checked_by_etag = 0, 0
    if _head(s3_client, bucket, manifest_key(target, release)) is not None:
        manifest = publish.load_remote_json(s3_client, bucket, manifest_key(target, release))
        held = _list(s3_client, bucket, target_folder)
        missing = [name for name in _release_keys(manifest) if f"{target_folder}{name}" not in held]
        if missing:
            raise Refused(
                f"{target}'s {release} folder lacks {len(missing)} of the keys its manifest lists "
                f"(first: {missing[0]}), so its phones would 404 them. The pointer was not moved."
            )
    elif source == target:
        raise Refused(f"{manifest_key(target, release)} is not in the bucket, so {target} cannot roll back to {release}.")
    else:
        objects = _list(s3_client, bucket, folder)
        source_manifest = manifest_key(source, release)
        if source_manifest not in objects:
            raise Refused(f"{source_manifest} is not in the bucket, so {source} holds no {release} to promote.")
        manifest = publish.load_remote_json(s3_client, bucket, source_manifest)
        missing = [name for name in _release_keys(manifest) if f"{folder}{name}" not in objects]
        if missing:
            raise Refused(
                f"{source}'s {release} folder lacks {len(missing)} of the keys its manifest lists "
                f"(first: {missing[0]}), so it is not a whole release. Nothing was copied."
            )
        destination = {key: f"{target_folder}{key[len(folder) :]}" for key in objects}
        assert_valid_keys(list(destination.values()))

        def copy_one(key: str) -> str:
            s3_client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": key}, Key=destination[key])
            return key

        def check_one(key: str) -> tuple[str, bool]:
            return key, _same(objects[key], _head(s3_client, bucket, destination[key]))

        # Every object but the manifest, then the check, then the manifest:
        # a target manifest is what says the folder is whole, to this module
        # on a rerun and to every deploy guard and phone.
        body = [key for key in objects if key != source_manifest]
        publish._in_parallel([partial(copy_one, key) for key in body])
        wrong = [key for key, ok in publish._in_parallel([partial(check_one, key) for key in body]) if not ok]
        if wrong:
            raise Refused(
                f"{len(wrong)} copied object(s) do not match their source (first: {destination[wrong[0]]}). "
                f"{target}'s {release} manifest was not written and the pointer was not moved."
            )
        copy_one(source_manifest)
        if not _same(objects[source_manifest], _head(s3_client, bucket, destination[source_manifest])):
            raise Refused(f"{destination[source_manifest]} does not match its source. The pointer was not moved.")
        copied = len(objects)
        checked_by_etag = sum(1 for entry in objects.values() if "-" not in (entry.get("etag") or "-").strip('"'))

    move = move_pointer(
        environment=target,
        release=release,
        schema_version=schema_version,
        reason=f"promoted from {source}" if source != target else f"rolled back within {target}",
        s3_client=s3_client,
        bucket=bucket,
        provenance=provenance,
        now=now,
    )
    return {**move, "copied": copied, "checked_by_etag": checked_by_etag}


def _release_keys(manifest: dict | None) -> list[str]:
    """The keys a release folder must hold: its manifest's release-scoped artifacts."""
    artifacts = (manifest or {}).get("artifacts")
    if not isinstance(artifacts, dict):
        raise Refused("The release's manifest lists no artifacts, so it cannot be checked whole.")
    return sorted(name for name in artifacts if releases.is_release_artifact(name))


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    move = commands.add_parser("move", help="point one environment at a release its own tree holds")
    move.add_argument("--environment", required=True, choices=data_env.ENVIRONMENTS)
    move.add_argument("--release", required=True)
    move.add_argument("--schema-version", default=DEFAULT_SCHEMA_VERSION)
    move.add_argument("--reason", default="moved by hand")
    promote_parser = commands.add_parser("promote", help="copy a release into an environment and point it there")
    promote_parser.add_argument("--to", dest="target", required=True, choices=data_env.ENVIRONMENTS)
    promote_parser.add_argument("--from", dest="source", default=data_env.UA, choices=data_env.ENVIRONMENTS)
    promote_parser.add_argument("--release", default=None, help="default: the release the source's pointer names")
    promote_parser.add_argument("--schema-version", default=DEFAULT_SCHEMA_VERSION)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = _arguments(argv if argv is not None else [])
    if args.command == "move":
        result = move_pointer(
            environment=args.environment, release=args.release, schema_version=args.schema_version, reason=args.reason
        )
    else:
        result = promote(target=args.target, source=args.source, release=args.release or None, schema_version=args.schema_version)
    environment, version = result["environment"], result["schema_version"]
    if result["moved"]:
        print(
            f"{environment}'s {version} pointer moved from {result['previous_release'] or 'nothing'} to "
            f"{result['release']}, recorded in {data_env.scope_key(environment, HISTORY_KEY)}."
        )
    else:
        print(f"{environment}'s {version} pointer already names {result['release']}; nothing was written.")
    if "copied" in result:
        print(f"Objects copied: {result['copied']}; of those, checked by ETag as well as size: {result['checked_by_etag']}.")
    return result


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (PermissionError, Refused, data_env.UnknownEnvironment) as exc:
        print(f"::error::{exc}")
        raise SystemExit(1)
