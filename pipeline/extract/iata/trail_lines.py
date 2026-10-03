"""Ice Age Trail Alliance: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch c10_nst_rest).

The loaded copy is a single merged line with no segment names. IATA's layers name every segment and
separate trail from connecting route. That split matters to a hiker: a road walk is not a trail.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Arrives via `wi-dnr` as `wi_ice_age_trail`: 1 polyline, 3 fields. IATA's own: "
        "`.../IAT_Segments1/FeatureServer/0` (the item `735b25ad50e74520b7396d9168f53cfc` the catalogue cites, "
        '"Official Layer"): 158 segments with `Segment` and `length_mi`, last edit 2026-09-18. '
        "`.../IAT_Connecting_Route/FeatureServer/0`: 98 road-walk segments. "
        "`.../IAT_Segments_CR/FeatureServer/0`: 256 segments with `Status`. "
        "`.../IAT_Spur_and_Loop_Trails/FeatureServer/8`: 217. ArcGIS layers; maxRecordCount 1,000; EPSG:3071.",
    ),
    where=(
        "https://dnrmaps.wi.gov/arcgis/rest/services",
        "https://iceagetrail.org/",
    ),
    reason="drawn from wi_dnr/'s resources, extracted once there (decision 34); checked names the layer this org's "
    "data arrives in",
)
