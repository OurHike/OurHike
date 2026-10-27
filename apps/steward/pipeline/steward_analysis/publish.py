"""Upload the scored files to Campsite Steward's private R2 bucket (decided by poll, 2026-10-27).

    python -m steward_analysis.publish            after build.py has written data/out/

The bucket is the maintainer's to create, private, with an R2 API token
limited to it. Its three secrets are this app's own, never OurHike's public
bucket's keys, because the files hold the location of every user-created
campsite in ATC's inventory (PLAN.md's opening section). Only the account's
endpoint is shared with OurHike's pipeline:

    R2_ENDPOINT_URL                 the account-scoped S3 endpoint (OurHike's, same account)
    STEWARD_R2_BUCKET               the private bucket
    STEWARD_R2_ACCESS_KEY_ID        a token scoped to that bucket alone
    STEWARD_R2_SECRET_ACCESS_KEY
    STEWARD_R2_WRITE_ENABLED=true   the write gate: nothing uploads without it, the same
                                    opt-in pipeline/publish.py requires of R2_WRITE_ENABLED

LAYOUT. Each run uploads under its own prefix and moves a pointer last:

    analysis/runs/<run id>/summary.json
    analysis/runs/<run id>/sites/<club>.json
    analysis/latest.json            {"run": "<run id>", "prefix": "analysis/runs/<run id>/", ...}

so a reader that follows `latest.json` never sees a run half uploaded, and a
failed upload leaves the previous run current. Old runs are kept: 4.3 MB a
week (measured 2026-10-26) is about 220 MB a year, and pruning can wait until
someone needs a year-old ranking back or the bucket's size matters.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import boto3

from steward_analysis.build import DEFAULT_DATA

WRITE_GATE = "STEWARD_R2_WRITE_ENABLED"
REQUIRED = ("R2_ENDPOINT_URL", "STEWARD_R2_BUCKET", "STEWARD_R2_ACCESS_KEY_ID", "STEWARD_R2_SECRET_ACCESS_KEY")
POINTER_KEY = "analysis/latest.json"

#: Private files, so nothing between the bucket and a reader should keep a copy.
CACHE_CONTROL = "private, no-store"


class PublishRefused(RuntimeError):
    pass


def client_from_env(env=os.environ):
    return boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT_URL"],
        aws_access_key_id=env["STEWARD_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["STEWARD_R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def check_env(env=os.environ) -> None:
    """Refuse by name: the gate first, then every missing secret at once."""
    if env.get(WRITE_GATE, "").strip() != "true":
        raise PublishRefused(f"{WRITE_GATE} is not 'true', so nothing was uploaded. A trusted job sets it deliberately.")
    missing = [name for name in REQUIRED if not env.get(name, "").strip()]
    if missing:
        raise PublishRefused(
            f"missing {', '.join(missing)}: the private bucket and its token are not set up yet (apps/steward/PLAN.md §11)"
        )


def files_to_upload(out_dir: Path) -> list[Path]:
    summary = out_dir / "summary.json"
    sites = sorted((out_dir / "sites").glob("*.json"))
    if not summary.is_file() or not sites:
        raise PublishRefused(f"{out_dir} holds no summary.json or no club files; run steward_analysis.build first")
    return [summary, *sites]


def publish(out_dir: Path, client, bucket: str, run_id: str | None = None) -> dict:
    """Upload one run under its own prefix, then point latest.json at it. Returns the pointer."""
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"analysis/runs/{run_id}/"
    files = files_to_upload(out_dir)
    for path in files:
        key = prefix + path.relative_to(out_dir).as_posix()
        client.put_object(
            Bucket=bucket, Key=key, Body=path.read_bytes(), ContentType="application/json", CacheControl=CACHE_CONTROL
        )
    summary = json.loads((out_dir / "summary.json").read_text())
    pointer = {
        "run": run_id,
        "prefix": prefix,
        "files": len(files),
        "generated_at": summary.get("generated_at"),
        "data_last_edited": (summary.get("source") or {}).get("data_last_edited"),
    }
    # Last, so a reader never follows the pointer into a run that is still uploading.
    client.put_object(
        Bucket=bucket,
        Key=POINTER_KEY,
        Body=json.dumps(pointer, indent=2).encode(),
        ContentType="application/json",
        CacheControl=CACHE_CONTROL,
    )
    return pointer


def main(argv: list[str] | None = None, env=os.environ) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="the data directory (default: %(default)s)")
    args = parser.parse_args(argv)
    check_env(env)
    pointer = publish(args.data / "out", client_from_env(env), env["STEWARD_R2_BUCKET"])
    # Counts only: a log line is not the place for a site's name or location.
    print(f"published run {pointer['run']}: {pointer['files']} files under {pointer['prefix']}, latest.json moved last")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
