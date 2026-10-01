"""Continental Divide Trail Coalition: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Format page. `cdtcoalition.org/explore-the-trail/day-section-hiking/` carries 10 named day and section"
        ' hikes (e.g. "East Shore Trail", "Lewis and Clark Pass via Alice Creek Trail").',
    ),
    where=("https://cdtcoalition.org/explore-the-trail/day-section-hiking/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
