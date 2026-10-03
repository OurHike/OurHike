"""Connecticut DEEP: points of interest, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

`WATER` = False on 194 trailheads is useful negative information ("no water here"). Only 2 say True.
Skeptic, 2026-10-01: also `CT_Coastal_Public_Access_Sites/FeatureServer/0` (owner a personal ArcGIS
account), 357 points, with `Fee`, `Directions` and `PhotoThr_1`. Its data was last edited …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`DEEP_Trails_Set/1` Trail Access: 209, with `PARKING`, `RESTROOM`, `WATER` (True 2 / False 194 / "
        "Unknown 13) and `OPENWHEN`. `DEEP_Trails_Set/2` Trail Interest: 296 (Scenic View 65, Bridge 53, Stream"
        " Crossing 7, Point of Interest 156). `DEEP_Property_Access_Locations/0`: 385, CC0, edited 2026-04-21, "
        "with `STATUS`, `CAMP_BCKPK`, `OVRLK_TOWR`, `HIKING`, `LINK`. `CT_Outdoor_Recreation_20160209` (10 "
        "layers, 2016, stale).",
    ),
    where=("https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/CT_Coastal_Public_Access_Sites/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
