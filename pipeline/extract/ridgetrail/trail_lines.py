"""Bay Area Ridge Trail Council: trail lines, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

The ArcGIS layer is the one to load: it is machine-readable, has `editingInfo` for change detection,
and was edited last month. The `Restricted` type and `/managed-access-trails/` (permit or guide
needed) must reach the hiker as access limits, not as an open trail. `nps_trails` covers only the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own ArcGIS: "
        "`https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services/Bay_Area_Ridge_Trail_Official_Public_Route_Update/FeatureServer/0`"
        ' ("Bay Area Ridge Trail Official Route Public", `RT_GISDepartment`, item modified 2026-09-08). 118 '
        "polylines, with a sum of `Calculated_Mileage` of ≈510 mi. Primary Dedicated is 56 segments, 301.7 mi. "
        'Primary "Dedicated (but not full Multi-Use)" is 22 segments, 89.0 mi. The rest is connector, parallel,'
        " spur, and Restricted (3 segments, 20.6 mi). 50 fields cover dogs, bikes, horses, restrooms, camping "
        "and parking fee. Files: GPX …",
    ),
    where=(
        "https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services/Bay_Area_Ridge_Trail_Official_Public_Route_Update/FeatureServer/0",
        "https://ridgetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
