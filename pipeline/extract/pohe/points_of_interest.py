"""Potomac Heritage Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c10_nst_rest).

The NVRC amenities were collected in Survey123. The schema carries `Management_Stakeholder`,
`Agency` and `Date_Field_Collection`, but no person or email field (unlike IATA's). The 46
"Pavilion/Covered Shelter" rows are picnic pavilions. They must not map to `shelter`, because a
hiker reading …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The association still publishes none (pages `/maps`, `/about`, `/phta-news`, sitemap), and the NPS POI"
        " layer still has `UNITCODE='POHE'` = 0. NPS `POHE_GIS`: "
        "`POHE_Potomac_Heritage_Trail_Mile_Markers_View/0` has 356 mile markers (`Mile`, `TrailName`, "
        "`Jurisdiction`; last edit 2022-06-15). `POHE_Scenic_View_Points/0` has 116 viewpoints (last edit "
        "2024-12-13), with `photo_url` and `photo_use`. NVRC: `PHNST_Wayfinding_Amenities_Assessment/2` PHNST "
        "Amenities has 1,005 points, last edit 2025-07-29: Bench 291, Trash Bin 256, Picnic Table 108, "
        "Recycling 72, Restrooms 63, Bike Rack 51 …",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/pohe/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
