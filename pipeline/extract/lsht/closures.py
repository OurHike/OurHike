"""Lone Star Hiking Trail Club: closures, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The 2024 GeoJSON is stale-risk. The club says "the USFS website is the official position."

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'GeoJSON "Closed Trail Sections" (`26ead23c99224bdaac4702a269306301`, "Sections of LSHT System '
        'currently closed to hikers", 59,545 B, 2024-06-23), a layer of web map '
        '`661f31eba56644f09d5908a6b21ed4b8`. The Thru Hike page: "The bridge over the East Fork of the San '
        "Jacinto River at Mile 71.1 is washed out … An unmarked, unofficial, and difficult to follow detour has"
        ' been mapped".',
    ),
    where=("https://lonestartrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
