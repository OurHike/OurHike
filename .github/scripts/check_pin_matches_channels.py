"""Refuse a deploy whose DATA_RELEASE and channels.json entry name two releases (pipeline/ELT.md decision 145).

    DATA_URL=https://... python3 .github/scripts/check_pin_matches_channels.py

A phone reads the compiled `DATA_RELEASE` (client/src/lib/dataRelease.ts)
until it has read the pointer. On launch, lib/dataChannel.ts's readDataChannel
reads `channels.json` at the data base and records the release it names for
this phone's data environment and schema version, and from the next launch
dataRelease.ts's SESSION_RELEASE reads that record. So a build whose two values
disagree ships a phone that reads one release on its first launch and switches
to the other on the launch after it reads the pointer. That is overnight
offline review 1, finding 7, on the branch of PR #1805 — dlt → dbt re-platform
as one go/no-go change, where DATA_RELEASE is 2026-10-03-2 and production's
entry 2026-09-24-2.

THE ENVIRONMENT is read off DATA_URL the way lib/dataRelease.ts's
environmentOf reads it off the build's VITE_DATA_BASE_URL: a base ending
`/environments/<name>` is <name>, anything else is production. pages.yml
therefore checks production's entry and ua.yml UA's, and a UA_DATA_BASE_URL
override pointing at production's root checks production's, which is the entry
such a build's phones take.

THE COMMITTED channels.json, not the copy uploaded at the data base, and no
network. The step before this one in both workflows, "Confirm channels.json's
release exists", fails when an uploaded copy names another release than the
committed entry; together the two hold the copy a phone reads to the release
it starts on. Reading only the commit also means this refuses a disagreeing
pair whatever the bucket holds, before production is filled or after.

Exit 0 when the two agree, and when DATA_URL is empty: a build with no data
base reads no pointer at all (readDataChannel answers `unconfigured`). Exit 1
when they disagree, when channels.json names no entry for this environment and
schema version, and when either file cannot be read the way this expects:
a constant that moved must update this check, not leave it checking nothing.

Not run by pr-preview.yml, which carries none of this family of checks: its
data environment is chosen at run time (production, or UA when production does
not hold the pin, or either by dispatch), it never checks the uploaded copy,
and it is torn down when its pull request closes. RELEASING.md §10 says what to
do when this fails.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RELEASE_FILE = REPO_ROOT / "client" / "src" / "lib" / "dataRelease.ts"
CHANNELS_FILE = REPO_ROOT / "channels.json"
#: The lines pages.yml's and ua.yml's checks read with `sed -n "s/^export const DATA_RELEASE = '\(.*\)'$/\1/p"`.
DATA_RELEASE_LINE = re.compile(r"^export const DATA_RELEASE = '(.*)'$", re.MULTILINE)
SCHEMA_LINE = re.compile(r"^export const DATA_SCHEMA_VERSION = '(.*)'$", re.MULTILINE)
#: A release id, as dataRelease.ts's RELEASE_ID spells one: `2026-09-24`, `2026-09-24-2`.
RELEASE_ID = re.compile(r"\d{4}-\d{2}-\d{2}(?:-\d+)?")
SCHEMA_VERSION = re.compile(r"v\d+")
#: dataRelease.ts's environmentOf, `/\/environments\/([a-z][a-z0-9_]*)\/*$/`.
ENVIRONMENT_SUFFIX = re.compile(r"/environments/([a-z][a-z0-9_]*)/*$")


class Refused(Exception):
    """A file is not shaped the way this check reads it, or names no entry to compare."""


def environment_of(base: str) -> str:
    """The data environment a base URL serves, as the client works it out."""
    match = ENVIRONMENT_SUFFIX.search(base)
    return match.group(1) if match else "production"


def _shown(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def pinned(source: str, shown: str) -> tuple[str, str, int]:
    """DATA_RELEASE, DATA_SCHEMA_VERSION and DATA_RELEASE's line number, out of dataRelease.ts's source."""
    release = DATA_RELEASE_LINE.search(source)
    if release is None or not RELEASE_ID.fullmatch(release.group(1)):
        raise Refused(
            f"Could not read a release id out of {shown}'s DATA_RELEASE. It has been restructured, and "
            ".github/scripts/check_pin_matches_channels.py must be updated rather than left checking nothing."
        )
    schema = SCHEMA_LINE.search(source)
    if schema is None or not SCHEMA_VERSION.fullmatch(schema.group(1)):
        raise Refused(
            f"Could not read a schema version out of {shown}'s DATA_SCHEMA_VERSION. It has been restructured, and "
            ".github/scripts/check_pin_matches_channels.py must be updated rather than left checking nothing."
        )
    return release.group(1), schema.group(1), source.count("\n", 0, release.start()) + 1


def channel_entry(text: str, environment: str, schema: str, shown: str) -> str:
    """channels.json's release for `environment` and `schema`, or Refused.

    An entry that is not a release id is refused without being repeated: the
    message is a workflow command, and the entry is text this did not choose."""
    try:
        document = json.loads(text)
    except ValueError as error:
        raise Refused(f"{shown} is not JSON ({error.msg}), so nothing says which release this build's phones follow.") from None
    channel = document.get(environment) if isinstance(document, dict) else None
    entry = channel.get(schema) if isinstance(channel, dict) else None
    if entry is None:
        raise Refused(
            f"{shown} names no {schema} release for {environment}, so this check cannot confirm that a phone of this "
            f"build stays on one release. Add {environment}'s {schema} entry, naming the release DATA_RELEASE names."
        )
    if not isinstance(entry, str) or not RELEASE_ID.fullmatch(entry):
        raise Refused(f"{shown}'s {environment} {schema} entry is not a release id, so a phone would ignore it.")
    return entry


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--client", type=Path, default=DATA_RELEASE_FILE, help="dataRelease.ts to read DATA_RELEASE from")
    parser.add_argument("--channels", type=Path, default=CHANNELS_FILE, help="channels.json to read the entry from")
    args = parser.parse_args(argv)

    base = os.environ.get("DATA_URL", "").strip()
    if not base:
        print(
            "No data source configured - skipping the check. A build with no data base reads no channels.json "
            "(lib/dataChannel.ts answers `unconfigured`), so its phones read DATA_RELEASE alone."
        )
        return 0
    environment = environment_of(base)
    client, channels = _shown(args.client), _shown(args.channels)
    try:
        if not args.client.is_file():
            raise Refused(f"{client} does not exist, so there is no DATA_RELEASE to compare.")
        release, schema, line = pinned(args.client.read_text(encoding="utf-8"), client)
        if not args.channels.is_file():
            raise Refused(f"{channels} does not exist, so nothing says which release this build's phones follow.")
        entry = channel_entry(args.channels.read_text(encoding="utf-8"), environment, schema, channels)
    except Refused as refused:
        print(f"::error::{refused}")
        return 1

    print(f"Data environment: {environment}, read off DATA_URL as lib/dataRelease.ts's environmentOf reads it.")
    print(f"DATA_RELEASE, what a phone reads on its first launch: {release} ({client}:{line}).")
    print(f"channels.json's {environment} {schema} entry, what it follows once it has read the pointer: {entry} ({channels}).")
    if entry != release:
        print(
            f"::error::DATA_RELEASE is {release} and channels.json's {environment} {schema} entry is {entry}, so a phone "
            f"installing this build reads {release} on its first launch and switches to {entry} on the launch after it "
            f"reads the pointer (pipeline/ELT.md decision 145). Move both to one release {environment} holds, in one "
            "commit, as the release train does (RELEASING.md §10), and deploy that commit."
        )
        return 1
    print(f"They agree: a phone of this build reads {release} before the pointer and after it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
