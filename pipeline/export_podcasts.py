"""Publish the podcast episodes picked for each hike (#1683 - Offer podcast
episodes picked for the hike, with a one-tap Spotify save and an in-app player).

    python export_podcasts.py            check the list, write data/podcasts/episodes.json
    python export_podcasts.py --upload   ...and put it at podcasts/episodes.json in R2

WHAT THIS READS. reference/podcast_episodes.json and nothing else - no
network, no other artifact. lib/podcasts.py is the gate a row passes.

WHERE IT GOES, AND WHY NOT A RELEASE FOLDER. `podcasts/episodes.json` at the
bucket root, beside `conditions/` and `archive/`, which the phone reads
outside the pinned release (client/src/lib/dataRelease.ts's
ROOT_SCOPED_PREFIXES). The maintainer's decision, 2026-09-26, on #1683: the
list is live, so an episode added here reaches a phone on its next fetch with
no app release. A release-scoped artifact would have needed a data publish, a
DATA_RELEASE bump and an app release per episode. The price is that this one
object is rewritten in place, so a bad upload is served until the next one;
the gate below is what keeps a bad upload from happening.

A LIST THAT DROPPED A ROW IS NOT UPLOADED. A curated list quietly shrinking
is the failure export_highlights.py names ("the failure nobody notices"), and
here it would also replace a good list already on phones. So a drop fails the
run before anything is written to the bucket.

RUN BY .github/workflows/publish-podcasts.yml, dispatched by a person. No
schedule and no push trigger, like every other publishing workflow here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from lib.data_env import resolve as resolve_environment
from lib.data_env import scope_key
from lib.podcasts import as_published, validate
from lib.r2_keys import validate_key

ROOT = Path(__file__).parent
REFERENCE_PATH = ROOT / "reference" / "podcast_episodes.json"
OUT_PATH = ROOT / "data" / "podcasts" / "episodes.json"

#: The one object this writes. Spelled here and read by the client's
#: lib/podcasts.ts; tests/test_published_key_contract.py holds the two
#: spellings together the way it holds every other key.
PODCASTS_KEY = "podcasts/episodes.json"

WRITE_ENABLED_ENV_VAR = "R2_WRITE_ENABLED"


def build_document(reference: dict) -> tuple[dict, list[tuple[str, str]]]:
    """The published document, and every row that could not be in it."""
    rows = reference.get("episodes")
    if not isinstance(rows, list):
        raise SystemExit(f"{REFERENCE_PATH} has no `episodes` list")
    result = validate(rows)
    document = {
        "source": "reference/podcast_episodes.json",
        "episodes": [as_published(episode) for episode in result.episodes],
    }
    return document, result.dropped


def render(document: dict) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def upload(path: Path, key: str = PODCASTS_KEY) -> str:
    """Put the list in the bucket, under the data environment's prefix.

    The same three guards archive_nynjtc_sheet_extents.py's upload keeps, in
    the same order: the key must be legal in this layout, the environment
    one of the three, and R2_WRITE_ENABLED exactly "true" - so a run by hand
    on a laptop with credentials in its environment writes nothing by
    accident.

    Cached for five minutes rather than the archive's hour: this object is
    meant to change, and a hiker who was told an episode is on the list
    should see it after a short wait, not after lunch.
    """
    reason = validate_key(key)
    if reason is not None:
        raise SystemExit(reason)
    if os.environ.get(WRITE_ENABLED_ENV_VAR) != "true":
        raise SystemExit(f"{WRITE_ENABLED_ENV_VAR} is not 'true', so nothing is uploaded. Set it to write to R2 on purpose.")
    environment = resolve_environment()
    scoped = scope_key(environment, key)

    import boto3  # here rather than at the top: checking the list needs no bucket credentials

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    client.put_object(
        Bucket=os.environ["R2_BUCKET"],
        Key=scoped,
        Body=path.read_bytes(),
        ContentType="application/json",
        CacheControl="public, max-age=300",
    )
    return scoped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--upload", action="store_true", help=f"after writing, put the file at {PODCASTS_KEY} in R2")
    args = parser.parse_args(argv)

    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    document, dropped = build_document(reference)

    if dropped:
        print(f"{len(dropped)} row(s) in {REFERENCE_PATH.name} cannot be published:", file=sys.stderr)
        for label, why in dropped:
            print(f"  {label}: {why}", file=sys.stderr)
        print("Nothing was written. Fix the rows above and run again.", file=sys.stderr)
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render(document), encoding="utf-8")
    episodes = document["episodes"]
    print(f"{len(episodes)} episode(s) -> {OUT_PATH}")
    for episode in episodes:
        anchors = [*episode["hikes"], *(f"mi {start:g}-{end:g}" for start, end in episode["at_miles"])]
        print(f"  {episode['spotify_id']}  {episode['show']}: {episode['title']}  [{', '.join(anchors)}]")

    if args.upload:
        scoped = upload(OUT_PATH)
        print(f"Uploaded to {scoped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
