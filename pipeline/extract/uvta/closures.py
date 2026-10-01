"""Upper Valley Trails Alliance: closures, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

One alerts channel for both closures and warnings. Poll 7's `obstructs_trail` rule splits them.
uvtrails.org search for "trail closure" found 6 hits, all op-eds.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('Trail Finder trail pages carry an "Alerts" tab. The Monadnock example reads "Day Use Reservation Required".',),
    where=("https://uvtrails.org",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
