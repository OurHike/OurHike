"""NC High Peaks Trail Association: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

The numbered USFS trails are likely also in `usfs_trails`, and the MST pieces in `nc_mst_trail` (R).
The club's own copy carries its own names. No ArcGIS items found.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "KML `https://nchighpeaks.org/interactivemaps/TrailSunday3.xml` (621,078 B, last-modified 2023-02-08), "
        "which `/interactivemaps/maps.htm` loads. 28 LineStrings: USFS trails 161–201 (Black Mountain Crest "
        "#179, Colbert Ridge #178…), Mount Mitchell SP trails, and 4 MST pieces.",
    ),
    where=(
        "https://nchighpeaks.org/interactivemaps/TrailSunday3.xml",
        "https://nchighpeaks.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
