"""US Army Corps of Engineers: closures, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Too stale and too local to count as a feed. Recorded so nobody re-finds it and thinks it is one.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Mobile District `.../Closed_Recreation_Area_Public_View/FeatureServer/0`: 2 polygons, last edit "
        "2023-03-18. Otherwise per-lake HTML pages.",
    ),
    where=("https://usace.army.mil/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
