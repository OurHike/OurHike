"""Buckeye Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Restricted.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '26 section pages ("What to expect", miles and off-road share, e.g. Whipple "58.2 total miles / 14.1 '
        'off-road miles (24.2%)"). `/hike/circuit-hiking`. "Hiker on the Go" maps are sold in print.',
    ),
    where=("https://buckeyetrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
