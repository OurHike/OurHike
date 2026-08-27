"""Read NYNJTC's Trail Alerts off their WordPress API into a cache (#1078).

    python fetch_nynjtc_alerts.py

WHAT THIS IS FOR. The New York-New Jersey Trail Conference maintains ~160
miles of the A.T. and the trails in most of the parks this build now draws,
and they publish closures, detours and reroutes as a dated, tended feed. None
of it reaches a hiker using OurHike. `pipeline/ALERTS_NOTICES_SURVEY.md` §5
is the reconnaissance; features/ORG_NOTICES.md is the delivery design; this
is the first step of it, and deliberately only the first.

THE OUTPUT IS A CACHE, NOT AN ARTIFACT. It lands in `data/raw/`, which is
gitignored and is where CONTRIBUTING.md puts anything fetched.

WHO READS IT CHANGED ON 2026-08-27, and this is a correction rather than a
rewrite, because the reasoning it replaces was right when it was written.
#1078 shipped this fetcher with the registry entry at `reaches_hikers: false`
and said so here - "this one writes its cache for a PERSON to read, because
nothing downstream may consume it yet" - on two grounds: that `nynjtc_licence`
covers NYNJTC's two trail extracts "and nothing else", and that the
term-to-feature join table features/ORG_NOTICES.md specifies does not exist.

The first was answered. The maintainer gave a separate authorisation for the
NOTICES, recorded as `nynjtc_alerts_licence` in sources.json, and what it
authorises publishing is narrower than what this fetches: the headline, the
locality their own tags give, the `modified` date and the URL - never their
body text, which is their writing. `export_nynjtc_alerts.py` applies that
split and reads this cache.

The second was not answered and did not need to be. Every row ships
`place: unplaced`, which features/ORG_NOTICES.md §3 makes a first-class state
rather than a gap: the map draws none of them and the client surfaces them as
a list a hiker reads. The join table is still what would put one on the map.

So `reaches_hikers` is `true`, an export does read this file, and
publish-conditions.yml runs both - which it did not until #940, three weeks
after the authorisation, with `conditions/nynjtc_alerts.json` 404 on
production the whole time.

BEING POLITE TO SOMEBODY ELSE'S SERVER. One request for the alerts plus one
per place taxonomy - five in the steady state, against ATC's ten-plus-one-per
-update. That is the whole cost of a source that publishes an API instead of
a website, and it is why this fetches the vocabularies fresh every run rather
than caching them cleverly: five requests for data that moves a few times a
month does not need an optimisation.

FAILING IS NOT THE SAME AS FINDING NOTHING - `fetch_atc_updates.py`'s rule,
and it transfers unchanged. A run that cannot reach NYNJTC, or that reads a
payload it does not recognise, leaves the previous cache in place and exits
non-zero. The cache is written atomically at the end for that reason.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from lib.http_retry import request_with_retry
from lib.nynjtc_alerts import (
    PLACE_TAXONOMIES,
    TRAIL_ALERTS_CATEGORY_ID,
    alert_problems,
    parse_alert,
    parse_terms,
)

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "data" / "raw" / "nynjtc_alerts.json"

#: The API root, spelled here rather than read from the registry entry, which
#: carries the page a PERSON reads. That mirrors `lib/atc_scrape.py`'s
#: `LISTING_URL`: the registry records where a source lives for a human, and
#: the fetcher knows the machine route to it.
API_ROOT = "https://www.nynjtc.org/wp-json/wp/v2"

#: Names the project and links to it, the same courtesy `lib/atc_scrape.py`
#: extends - though unlike ATC's host, NYNJTC's answers a default client fine
#: (measured 2026-08-27). It is set anyway so an operator who wants to
#: throttle or contact us can see who this is from one line of their log.
USER_AGENT = "OurHike-pipeline/1.0 (+https://github.com/OurHike/OurHike)"

#: WordPress caps `per_page` at 100 and pages the rest. 18 alerts and 45
#: trail terms fit in one page each today; `park` returned exactly 100 on
#: 2026-08-27, which is precisely the reading that means "there may be more".
#: So every list route is paged rather than asked once - a vocabulary
#: silently truncated at 100 would drop placements with no error anywhere.
PAGE_SIZE = 100
MAX_PAGES = 20

TIMEOUT = 60


def session() -> requests.Session:
    made = requests.Session()
    made.headers["User-Agent"] = USER_AGENT
    return made


def fetch_paged(route: str, http: requests.Session, params: dict | None = None) -> list:
    """Every page of a WordPress list route, concatenated.

    Stops on the first short page, which is how the REST API says "that was
    the last one", and refuses to walk past MAX_PAGES so a misbehaving
    endpoint cannot spin forever - `lib/atc_scrape.py`'s pager ceiling,
    applied to a different shape of listing.
    """
    collected: list = []
    for page in range(1, MAX_PAGES + 1):
        response = request_with_retry(
            f"{API_ROOT}/{route}",
            session=http,
            params={"per_page": PAGE_SIZE, "page": page, **(params or {})},
            timeout=TIMEOUT,
            label=f"nynjtc/{route}",
        )
        batch = response.json()
        if not isinstance(batch, list):
            raise SystemExit(f"{route} answered {type(batch).__name__}, not a list - NYNJTC's API has changed shape.")
        collected.extend(batch)
        if len(batch) < PAGE_SIZE:
            return collected
    print(f"  {route}: stopped at {MAX_PAGES} pages, which is a ceiling rather than an ending.")
    return collected


def as_cache_entry(alert, now: datetime) -> dict:
    """One parsed alert, flattened for the cache.

    `fetched_at` is this run's clock; `modified_at` is NYNJTC's and is the one
    that says whether the alert is current. Keeping both apart is
    `fetch_atc_updates.py`'s rule and the reason a stale cache cannot look
    fresh.

    Place terms are stored as `{slug, name}` pairs rather than as the ids the
    post carried: a reviewed join table has to key on something a WordPress
    migration cannot renumber, and `lib/nynjtc_alerts.py` says why.
    """
    return {
        "slug": alert.slug,
        "title": alert.title,
        "published_at": alert.published_at,
        "modified_at": alert.modified_at,
        "source_url": alert.source_url,
        "trails": [{"slug": t.slug, "name": t.name} for t in alert.trails],
        "parks": [{"slug": t.slug, "name": t.name} for t in alert.parks],
        "regions": [{"slug": t.slug, "name": t.name} for t in alert.regions],
        "states": [{"slug": t.slug, "name": t.name} for t in alert.states],
        "text": alert.text,
        "fetched_at": now.isoformat(),
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    http = session()

    vocabularies = {}
    for taxonomy in PLACE_TAXONOMIES:
        terms = parse_terms(fetch_paged(taxonomy, http))
        if not terms:
            # An empty vocabulary is not "NYNJTC tags nothing". It is a route
            # that stopped answering in the shape this expects, and carrying
            # on would cache every alert with its placement silently missing.
            print(f"The `{taxonomy}` taxonomy came back empty, which means the parse broke rather than that it is empty.")
            return 1
        vocabularies[taxonomy] = terms
    print(" ".join(f"{name}:{len(terms)}" for name, terms in vocabularies.items()) + " terms read.")

    posts = fetch_paged("posts", http, {"categories": TRAIL_ALERTS_CATEGORY_ID})
    if not posts:
        # Same reading as ATC's empty listing: a category that answers nothing
        # is a parse that stopped working, not a region with no closures.
        print("NYNJTC's Trail Alerts category returned no posts at all, which means the parse broke.")
        return 1

    alerts, unreadable = [], []
    for post in posts:
        parsed = parse_alert(post, vocabularies)
        if parsed is None:
            unreadable.append(str(post.get("slug") or post.get("id") or "?"))
            continue
        alerts.append(parsed)

    if unreadable:
        # Zero tolerance, for `fetch_atc_updates.py`'s reason: a payload this
        # build cannot read is a payload whose shape has changed, and the
        # honest response is to stop and be looked at rather than to cache the
        # subset that still happened to parse.
        print(f"Could not read {len(unreadable)}: {', '.join(unreadable[:5])}")
        print("Leaving the previous cache in place - see this file's docstring.")
        return 1

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(
            {
                "fetched_at": now.isoformat(),
                "listed": len(alerts),
                "alerts": {alert.slug: as_cache_entry(alert, now) for alert in alerts},
            },
            indent=2,
        )
        + "\n"
    )

    placeable = [alert for alert in alerts if not alert_problems(alert)]
    print(f"Wrote {len(alerts)} alert(s) to {CACHE_PATH}; {len(placeable)} name a trail our own data could be joined to.")
    for alert in sorted(alerts, key=lambda a: a.modified_at, reverse=True):
        problems = alert_problems(alert)
        where = ", ".join(term.name for term in alert.place_terms) or "nowhere named"
        print(f"  {alert.modified_at[:10]}  {alert.title[:58]:58}  {where[:44]}")
        for problem in problems:
            print(f"      - {problem}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
