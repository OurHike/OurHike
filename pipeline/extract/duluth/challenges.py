"""City of Duluth Open Data: challenges, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`duluthmn.gov/parks/`: 0 matches for "challenge" or "passport".',
        "Skeptic adds: the same brochure search found no passport or patch programme.",
    ),
    where=("https://duluthmn.gov/parks/",),
)
