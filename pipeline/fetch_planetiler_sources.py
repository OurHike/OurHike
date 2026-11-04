"""Put Planetiler's three profile sources in data/sources/ before the
basemap build asks for them (#1970).

Usage: python fetch_planetiler_sources.py [--max-age-days N]

build-basemap.yml runs this between restoring the Actions cache and
"Build the basemap". It keeps each file the cache restored, fetches one that
is missing or MAX_AGE_DAYS old, and keeps an older copy when a refetch
fails. lib/planetiler_sources.py says why Planetiler is not left to fetch
them itself: a 10-second wait it cannot be told to extend, which ended runs
57 and 58 after 12 to 19 minutes of work.

Exits 1, with the source and the reason, when a source has no copy and
cannot be fetched. That happens in this step, seconds into the job, rather
than after the state extracts. Writes `fetched=true` to $GITHUB_OUTPUT as
soon as anything new lands, so the save step keeps it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from lib.planetiler_sources import (
    MAX_AGE_DAYS,
    SOURCES_DIR,
    SourceUnavailable,
    ensure_sources,
    github_output_marker,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=MAX_AGE_DAYS,
        help=f"refetch a source at least this many days old (default {MAX_AGE_DAYS})",
    )
    args = parser.parse_args(argv)

    today = datetime.now(timezone.utc).date()
    try:
        outcomes = ensure_sources(
            SOURCES_DIR,
            today=today,
            max_age_days=args.max_age_days,
            on_fetched=github_output_marker(),
        )
    except SourceUnavailable as error:
        print(f"::error::Planetiler's profile sources are incomplete: {error}")
        return 1

    for outcome in outcomes:
        line = f"{outcome.name}: {outcome.action} - {outcome.detail}"
        print(f"::warning::{line}" if outcome.action == "kept_stale" else line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
