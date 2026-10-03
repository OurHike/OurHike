"""Pacific Crest Trail Association: photos, could not be told (coverage audit 2026-10-01, batch
b7_long_trails_states).

Still UNKNOWN. The one unread place is the photo contest's rules, which are what would say whether
entries are licensed beyond PCTA.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No openly licensed photo collection among the ArcGIS items (first 100 read, 283 scanned by keyword). "
        "The website could not be opened.",
        'Skeptic adds: all 300 items were scanned. The only image-like ones are basemaps and a "daily satellite'
        ' images" web map. `pcta.org/feed/?s=creative+commons` finds CC BY / CC BY-SA photos inside articles, '
        "but they are third-party Flickr photos credited to their authors, so they belong to `_shared/` "
        "Wikimedia/Flickr and are not PCTA's. `?s=photo+contest` finds 2024–2026 contest-winner posts with no "
        "licence in their text. The contest rules page was not found.",
    ),
    where=(
        "https://pcta.org/feed/?s=creative+commons",
        "https://pcta.org/",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
