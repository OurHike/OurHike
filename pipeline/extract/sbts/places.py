"""Sierra Buttes Trail Stewardship: places, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Businesses go stale. The hospital and post-office points matter most to a hiker, and they are five
years old.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"SBTS Amenities View Only", `SBTS_Amenities_View_Only/FeatureServer/0`: 466 trail-town service points.'
        " Restaurant 134, Lodging 67, Grocery 48, Post Office 32, Bar 28, Disc Golf 28, Brewery 21, Auto Parts "
        "19, Outdoor Gear 18, Bike Shop 17, Airport 16, Hospital 12, Coffee 10, Train Depot 9, Hardware 7. Data"
        " last edited 2021-03-21.",
    ),
    where=("https://services6.arcgis.com/t5asxkRF7xoBwgqv/arcgis/rest/services/SBTS_Amenities_View_Only/FeatureServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
