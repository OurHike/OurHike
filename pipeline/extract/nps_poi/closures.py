"""National Park Service: closures, drawn from nps/warnings.py's NPS alerts resource (decision 53,
phase B, 2026-10-03).

NPS's alerts land once, in nps/warnings.py's `nps_alerts`, for the park codes sources.json's entry
lists in `park_codes`, which are the codes club folders draw on. This folder's points are in every
NPS unit, and the units no club names are not read (622 alerts nationwide on 2026-10-03), so most of
this layer's parks get no NPS alert from there: the maintainer's call. NPS's `Park Closure` category
is the closures half, split from the rest in dbt; a Park Closure most often closes a facility or a
road rather than a trail, and no alert carries geometry, so it never sets `obstructs_trail` alone.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Keyed by `parkCode`, with no geometry: a closure names a park, not a segment. The `obstructs_trail`
split (decision 7) has to come from the category plus a reviewer, and an unclassified row goes to
warnings.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, the national list (the decision 53 inventory, batch 5, 2026-10-03): 622 alerts. "
            "nps/warnings.py's nps_alerts lands only the park codes club folders name, not this list."
        ),
        (
            "(coverage audit, 2026-10-01) NPS Data API `https://developer.nps.gov/api/v1/alerts` (JSON). 618 "
            "alerts nationwide. In a 100-alert sample: Park Closure 49, Information 28, Caution 20, Danger 3. "
            'Examples: "Trail Closures Due to Rockfall", "INNER CANYON TRAIL CLOSURES". Skeptic spot check: 617 '
            "today."
        ),
        (
            "(coverage audit, 2026-10-01) Skeptic adds: every alert carries a `relatedRoadEvents` field, and the "
            "API has a `/roadevents` endpoint. Its count is UNKNOWN because `DEMO_KEY` was rate-limited before it "
            "answered."
        ),
    ),
    where=("https://developer.nps.gov/api/v1/alerts",),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
