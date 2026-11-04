"""Put Planetiler's three profile sources in data/sources/ before the
basemap build asks for them (#1970).

Usage: python fetch_planetiler_sources.py [--max-age-days N]

build-basemap.yml runs this between restoring the Actions cache and
"Build the basemap". Each source comes from the first of the cache's copy,
the raw bucket's copy and its own host that is younger than MAX_AGE_DAYS,
and when its host fails, an older copy stands (lib/planetiler_sources.py,
"WHERE EACH SOURCE COMES FROM"). That module also says why Planetiler is not
left to fetch them itself: a 10-second wait it cannot be told to extend,
which ended runs 57 and 58 after 12 to 19 minutes of work.

THE RAW BUCKET is read and written only when all four RAW_BUCKET_SETTINGS
are set, as build-basemap.yml sets them on this step and on no other.
Without them this warns and asks the hosts alone. Each request to the bucket
gets botocore's own limits, read from botocore 1.43.123 on 2026-11-04: 60 s
to connect, 60 s to read, and five attempts. The bucket's manifest is read
first, and a failed read turns the bucket off for the run, so a bucket that
never answers costs about five minutes once, not once per source.

Exits 1, with the source and the reason, when a source has no copy and
cannot be fetched. That happens in this step, about two minutes into the
job, rather than after the state extracts. Writes `fetched=true` to
$GITHUB_OUTPUT as soon as anything new lands, so the save step keeps it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from boto3.exceptions import Boto3Error
from botocore.exceptions import BotoCoreError, ClientError

import publish
from lib.planetiler_sources import (
    BUCKET_PREFIX,
    MANIFEST_NAME,
    MAX_AGE_DAYS,
    SOURCES_DIR,
    WARNINGS,
    CopyFailed,
    Outcome,
    SourceUnavailable,
    ensure_sources,
    github_output_marker,
)

#: What this step needs set to use the bucket's copy: the account's
#: endpoint, and the raw store's bucket and key. Never the public bucket's
#: key, which only build-basemap.yml's publish job holds.
RAW_BUCKET_SETTINGS = ("R2_ENDPOINT_URL", "R2_RAW_BUCKET", "R2_RAW_ACCESS_KEY_ID", "R2_RAW_SECRET_ACCESS_KEY")

#: What the bucket's client raises when its store refuses or does not
#: answer: botocore's request errors and error responses, and boto3's
#: transfer errors (S3UploadFailedError, RetriesExceededError).
BUCKET_FAILURES = (BotoCoreError, ClientError, Boto3Error)


def _why(error: BaseException) -> str:
    return f"{type(error).__name__}: {' '.join(str(error).split())}"


class RawBucketCopy:
    """lib/planetiler_sources.py's SourceCopy in the raw store's bucket: each
    source at BUCKET_PREFIX/<its filename>, with the manifest beside them."""

    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def _key(self, filename: str) -> str:
        return f"{BUCKET_PREFIX}/{filename}"

    def read_manifest(self) -> dict | None:
        try:
            return publish.load_remote_json(self.client, self.bucket, self._key(MANIFEST_NAME))
        except BUCKET_FAILURES as error:
            raise CopyFailed(_why(error)) from error

    def get(self, filename: str, dest: Path) -> None:
        try:
            self.client.download_file(self.bucket, self._key(filename), str(dest))
        except BUCKET_FAILURES as error:
            raise CopyFailed(_why(error)) from error

    def put(self, path: Path, filename: str) -> None:
        try:
            self.client.upload_file(str(path), self.bucket, self._key(filename))
        except BUCKET_FAILURES as error:
            raise CopyFailed(_why(error)) from error

    def write_manifest(self, manifest: dict) -> None:
        body = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        try:
            self.client.put_object(Bucket=self.bucket, Key=self._key(MANIFEST_NAME), Body=body)
        except BUCKET_FAILURES as error:
            raise CopyFailed(_why(error)) from error


def raw_bucket_copy() -> tuple[RawBucketCopy | None, list[str]]:
    """The bucket's copy, opened with the raw store's key, or None and the
    names of the settings that are not set."""
    missing = [name for name in RAW_BUCKET_SETTINGS if not os.environ.get(name)]
    if missing:
        return None, missing
    client = publish.r2_client(key_pair=(os.environ["R2_RAW_ACCESS_KEY_ID"], os.environ["R2_RAW_SECRET_ACCESS_KEY"]))
    return RawBucketCopy(client, os.environ["R2_RAW_BUCKET"]), []


def _print(outcomes: list[Outcome]) -> None:
    for outcome in outcomes:
        line = f"{outcome.name}: {outcome.action} - {outcome.detail}"
        print(f"::warning::{line}" if outcome.action in WARNINGS else line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=MAX_AGE_DAYS,
        help=f"refetch a source at least this many days old (default {MAX_AGE_DAYS})",
    )
    args = parser.parse_args(argv)

    copy, missing = raw_bucket_copy()
    if copy is None:
        print(
            f"::warning::No raw bucket this run ({', '.join(missing)} not set): a source the cache lacks comes from its host alone."
        )

    today = datetime.now(timezone.utc).date()
    try:
        outcomes = ensure_sources(
            SOURCES_DIR,
            today=today,
            max_age_days=args.max_age_days,
            on_fetched=github_output_marker(),
            copy=copy,
        )
    except SourceUnavailable as error:
        _print(error.outcomes)
        print(f"::error::Planetiler's profile sources are incomplete: {error}")
        return 1

    _print(outcomes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
