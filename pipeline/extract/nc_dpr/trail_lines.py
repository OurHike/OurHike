"""NC Division of Parks & Recreation — NC Trails: trail lines, drawn from another folder's resource
(coverage audit 2026-10-01, batch c9_federal_state_rest).

See the provenance finding above. The steward-owned layer is the better upstream. Also out there: a
personal ArcGIS account's "NC State Park Trails"
(`services1.arcgis.com/PwLrOgCfU0cYShcG/.../NC_State_Park_trails`), a third party (NEMAC), not DPR.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Via `nc-mst` → `nc_mst_trail` (328 features, last edit 2020-10-19). DPR publishes its own: "
        "`State_Trails/FeatureServer/1`, 1,065 segments across 16 `SYSTEMNAME` values: MST 402, East Coast "
        "Greenway 380, Overmountain Victory 55, Fonta Flora 45, Hickory Nut Gorge 32, Roanoke River 29, Deep "
        "River 25, Wilderness Gateway 24, Yadkin River 18, Dan River 16, Haw River 14, Equine 11, Northern "
        "Peaks 7, French Broad 5, First Broad 1, South Fork 1. Fields include `TRAILSTAT`, `WEBLINK` and "
        "`Blaze`.",
    ),
    where=(
        "https://services.nconemap.gov/secure/rest/services",
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
        "https://trails.nc.gov/",
    ),
    reason="drawn from nc_mst/'s resources, extracted once there (decision 34); checked names the layer this org's "
    "data arrives in",
)
