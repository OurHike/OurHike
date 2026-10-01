"""National Park Service: closures, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Keyed by `parkCode`, with no geometry: a closure names a park, not a segment. The `obstructs_trail`
split (decision 7) has to come from the category plus a reviewer, and an unclassified row goes to
warnings.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NPS Data API `https://developer.nps.gov/api/v1/alerts` (JSON). 618 alerts nationwide. In a 100-alert "
        'sample: Park Closure 49, Information 28, Caution 20, Danger 3. Examples: "Trail Closures Due to '
        'Rockfall", "INNER CANYON TRAIL CLOSURES". Skeptic spot check: 617 today.',
        "Skeptic adds: every alert carries a `relatedRoadEvents` field, and the API has a `/roadevents` "
        "endpoint. Its count is UNKNOWN because `DEMO_KEY` was rate-limited before it answered.",
    ),
    where=("https://developer.nps.gov/api/v1/alerts",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
