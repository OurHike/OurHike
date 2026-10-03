"""Florida Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

PDF. Skeptic spot-check: `/day-hike/` returns 200, and the Juniper Creek PDF returns 200
`application/pdf`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://floridatrail.org/day-hike/`: 16 "Grab-and-Go" hikes (carousel "1 of 16"), each a PDF with '
        "trailhead lat/long, key mileages and camping, e.g. "
        "`wp-content/uploads/2021/06/Juniper-Creek-Trail.pdf`. Also `/the-florida-trail-by-region/`.",
    ),
    where=(
        "https://floridatrail.org/day-hike/",
        "https://floridatrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
