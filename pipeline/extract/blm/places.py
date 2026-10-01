"""Bureau of Land Management: places, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

SMA says whose land a hiker stands on. It is useful for places, and it is large. Skeptic: PLAD says
where legal public access to BLM land exists. That makes it access data for the "get off the trail"
question (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`lands/BLM_Natl_NLCS_NM_NCA_poly/MapServer/1` (National Monuments, NCAs): 57; "
        "`lands/BLM_Natl_NLCS_WLD_WSA/MapServer/0` Wilderness 306, `/1` WSA 1,120; "
        "`recreation/BLM_Natl_Recreation/MapServer/9` Recreation Areas 588; "
        "`recreation/BLM_Natl_Recs_poly/MapServer/1` 3,477. Surface Management Agency: "
        "`lands/BLM_Natl_SMA_LimitedScale`.",
        "Skeptic adds (Measured): "
        "`https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/BLM_Natl_PLAD_Line/FeatureServer/0`"
        ' ("BLM Natl Public Lands Access Data Line") holds 4,835 lines; item modified 2026-09-25. A polygon '
        "twin exists.",
    ),
    where=(
        "https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/BLM_Natl_PLAD_Line/FeatureServer/0",
        "https://gis.blm.gov/arcgis/rest/services/lands/BLM_Natl_NLCS_NM_NCA_poly/MapServer/1",
        "https://gis.blm.gov/arcgis/rest/services/lands/BLM_Natl_NLCS_WLD_WSA/MapServer/0",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recreation/MapServer/9",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recs_poly/MapServer/1",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
