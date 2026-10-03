"""Wasatch Mountain Club: points of interest, published, and not landed (coverage audit 2026-10-01,
batch p08_persist).

Licence, UGRC: "The data, including but not limited to geographic data, tabular data, and analytical
data, are provided "as is" and "as available"… These data are provided as a public service for
informational purposes only." Class: none_stated (a disclaimer), presumed reusable under 21(a). …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "UGRC trailheads: "
        "`services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/UtahTrailheads/FeatureServer/0` (item "
        "`9c21cc1f…`, layer last edit 2026-03-07). 102 trailheads in the box. Fields `PrimaryName`, `Features`,"
        " `SeasonalRestriction`, `PrimaryMaintenance`; `PrimaryMaintenance` is null on all 102. USFS, LOADED: "
        "`usfs_rec_sites` has 73 sites in the box (TRAILHEAD 36, PICNIC SITE 18, CAMPGROUND 6). Water: USFS "
        "springs with `PUBLICINFO=1`: 58. WMC's own: the audit's sampled GPX has 0 `<wpt>`. The 157 KMZ could "
        "not be opened today because of the 406 wall, so whether a KMZ carries placemarks …",
    ),
    where=("https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/UtahTrailheads/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
