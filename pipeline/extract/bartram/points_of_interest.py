"""Bartram Trail Conference: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Page. About 13 trailheads. Water is prose, not points.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "13 BRBTC section pages (`crb_trail-sitemap.xml`, newest `lastmod` 2026-03-19). Each names a trailhead "
        'with decimal coordinates, e.g. `/trail/sandy-ford-to-warwoman-dell/`: "Sandy Ford Trailhead 34.8671, '
        '-83.2523". Each also gives length and prose on camping and water ("Campsites and water are sparse and '
        'in gaps…").',
    ),
    where=("https://bartramtrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
