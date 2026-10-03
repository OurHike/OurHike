"""AMC Connecticut Chapter: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Settled by skeptic, 2026-10-01: "Learn more…" points to `http://ct-amc.org/eor/HikerBadge.htm`,
which returns 404. The trail list is in the form PDF
`https://ct-amc.org/wp/wp-content/uploads/2019/07/EOR_HikerBadgeForm.pdf` (143,557 bytes,
last-modified 2019-07-21): 27 named trails (Bigelow Hollow …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "East of the River Hiker Badge, `/east-of-the-river/east-of-the-river-hiker-badge/` (page, 2019): a "
        "patch for completing a designated list of eastern CT trails.",
    ),
    where=(
        "https://ct-amc.org/wp/wp-content/uploads/2019/07/EOR_HikerBadgeForm.pdf",
        "https://ct-amc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
