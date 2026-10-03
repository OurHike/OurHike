"""The Mountaineers: points of interest, could not be told (coverage audit 2026-10-01, batch
p09_persist).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Tried: items 1 to 6 as for trail_lines. The Routes & Places parking coordinates (audit) cannot be "
        "read. KLF's `Access_Map_WFL1` (Forest Stand Access Map) holds plot points for field work, not POIs. "
        "The land managers' POIs come through `usfs_rec_sites` (LOADED).",
    ),
    where=(
        "https://services9.arcgis.com/fUZ4ZUl57GG2z81p/arcgis/rest/services",
        "https://mountaineers.org/",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
