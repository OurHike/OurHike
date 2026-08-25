"""Read ATC's Trail Updates off their website into a cache (#963).

    python fetch_atc_updates.py

WHAT THIS IS FOR. `reference/atc_updates.json` is a file in git, so its
content moves only when a pull request merges. The publish job around it has
been hourly since #720, which meant twenty-four bakes a day of frozen content:
a notice ATC posted on a Wednesday reached a hiker whenever somebody next
happened to look. **#478 - Upstream data freshness** flagged the source STALE
on 2026-08-13 and it sat eleven days; the page 2-10 review (**#945**) then
found 27 further in-effect updates that had never been published at all.

So this fetches ATC's pages as CONTENT rather than as a freshness signal, and
`export_atc_updates.py` publishes the mechanically unambiguous subset beside
the reviewed rows. What "unambiguous" means is `lib/atc_updates.py`'s
`auto_publish_refusal`, deliberately not here - this script does no judging.

THE OUTPUT IS A CACHE, NOT AN ARTIFACT. It lands in `data/raw/`, which is
gitignored and is where CONTRIBUTING.md puts anything fetched or derived. It
is not the reviewed file, it never becomes the reviewed file, and a person
editing `reference/atc_updates.json` is still the only way a row gets a band.

BEING POLITE TO SOMEBODY ELSE'S SERVER. Fetching all ten listing pages and all
89 updates every hour would be 99 requests an hour and 2,376 a day, for data
that moves a few times a month. So the listing is read every run - it is the
only way to learn that a slug exists - and an update's own page is asked for
only when it is new or when the cached copy has aged past `CACHE_TTL`. In the
steady state that is ten requests an hour plus one refresh per update per day.

FAILING IS NOT THE SAME AS FINDING NOTHING. A run that cannot reach ATC, or
that parses a page it does not recognise, leaves the previous cache in place
and exits non-zero. #463's rule - "their HTML is not an API… the job must fail
loudly and propose nothing rather than propose a partial set" - is the whole
reason the cache is written atomically at the end rather than per update.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib.atc_scrape import atc_session, fetch_listing_slugs, fetch_update, plan_fetches

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "data" / "raw" / "atc_updates.json"

#: How much of one run's parsing may fail before the whole run does. Zero:
#: a page this build cannot read is a page ATC has changed the shape of, and
#: the honest response is to stop and be looked at rather than to publish the
#: subset that still happened to parse.
TOLERATED_PARSE_FAILURES = 0


def load_cache(path: Path | None = None) -> dict:
    """What the last successful run learned, or an empty cache."""
    # Resolved here rather than in the signature: a default bound at
    # definition time captures the real path forever, which is invisible
    # until a test points CACHE_PATH somewhere else and is ignored.
    path = path or CACHE_PATH
    try:
        document = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    updates = document.get("updates")
    return updates if isinstance(updates, dict) else {}


def as_cache_entry(parsed, now: datetime) -> dict:
    """One parsed update, flattened for the cache.

    `fetched_at` is this run's clock and is what `plan_fetches` reads next
    time; `date_modified` is ATC's and is what decides whether a hiker sees
    the row. Keeping both is the point - one is about our copy, the other is
    about their page, and conflating them is how a stale cache would look
    fresh.
    """
    return {
        "slug": parsed.slug,
        "title": parsed.title,
        "category": parsed.category,
        "states": parsed.states,
        "date_modified": parsed.date_modified,
        "date_published": parsed.date_published,
        "miles": [{"direction": m.direction, "start": m.start, "end": m.end, "raw": m.raw} for m in parsed.miles],
        "text": parsed.text,
        "fetched_at": now.isoformat(),
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    session = atc_session()
    cache = load_cache()

    slugs = fetch_listing_slugs(session)
    if not slugs:
        # An empty listing is not "ATC has nothing posted". It is a parse that
        # stopped working, and treating it as the former would empty the
        # auto-published set on the next bake.
        print("ATC's listing yielded no updates at all, which means the parse broke.")
        return 1

    due = plan_fetches(slugs, cache, now)
    print(f"{len(slugs)} updates listed; {len(due)} to fetch, {len(slugs) - len(due)} from cache.")

    failures = []
    for slug in due:
        parsed = fetch_update(slug, session)
        if parsed is None:
            failures.append(slug)
            continue
        cache[slug] = as_cache_entry(parsed, now)

    if len(failures) > TOLERATED_PARSE_FAILURES:
        print(f"Could not parse {len(failures)}: {', '.join(failures[:5])}")
        print("Leaving the previous cache in place - see this file's docstring.")
        return 1

    # Slugs ATC no longer lists are KEPT rather than deleted, which is
    # discover_sources.py's posture for a vanished source and #463's open
    # question answered the same way: a notice disappearing is the weaker
    # signal of the two, and "we can no longer see it" is not "it reopened".
    # `listed` is what says which is which without throwing the copy away.
    listed = set(slugs)
    for slug, entry in cache.items():
        entry["listed"] = slug in listed

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(
            {"fetched_at": now.isoformat(), "listed": len(slugs), "updates": cache},
            indent=2,
        )
        + "\n"
    )
    dropped = sum(1 for entry in cache.values() if not entry["listed"])
    print(f"Wrote {len(cache)} update(s) to {CACHE_PATH}" + (f", {dropped} no longer listed." if dropped else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
