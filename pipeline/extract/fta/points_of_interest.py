"""Florida Trail Association: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

FTA publishes no water layer. `Dist2Water_ft` on campsites is the nearest thing to one.
`usfs_rec_sites` covers national-forest trailheads only. Skeptic: spot-checked `FT_Campsites/0` =
177 (last edit 2026-09-22) and `Trailheads_Public/0` = 166 (2026-09-22). "No water layer" holds. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../FT_Campsites/FeatureServer/0`: 177: Campsite 80, Designated Campsite 65, Campground 26, Shelter "
        "6. `Trail_Type` On Trail 130, On Spur 39, Off Trail 6. Each row has `Dist2Water_ft` and "
        "`Dist2Trail_ft`. Last edit 2026-09-22. `.../Trailheads_Public/FeatureServer/0`: 166, all "
        "`Trailhead_Status` Open, with `Capacity` and `Fee`.",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services",
        "https://floridatrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
