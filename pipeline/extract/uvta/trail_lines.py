"""Upper Valley Trails Alliance: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

Per-trail files, not one layer. Written consent needed. No ArcGIS items: 0 results for "Upper Valley
Trails Alliance".

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Trail Finder per-trail KML and GPX. The Mount Monadnock page links `kml/TrailLines702.kml` and "
        '`kml/gpx/TrailLines702..gpx`. The `/trails` listing reads "Showing 973 Trails".',
    ),
    where=("https://uvtrails.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
