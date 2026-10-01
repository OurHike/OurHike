"""Utah UGRC — SGID Trails and Pathways: points of interest, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

The springs belong in `_shared/usgs`, not here.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`UtahTrailheads/0`: 568, with `Features`, `SeasonalRestriction` (empty on all rows); last edit "
        "2026-03-07. `Campsites/2`: Utah State Parks campsites 3,663 (from Aspira, the reservation vendor), "
        "last edit 2026-07-29. `SpringsNHDHighRes/0`: 16,719 springs, from NHD, so really the USGS's. "
        "`HighestPeaks/0`: 113.",
    ),
    where=(
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
        "https://gis.utah.gov/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
