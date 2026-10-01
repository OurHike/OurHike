"""National Park Service: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c9_federal_state_rest).

The row is held on scope (corridor clip and a POITYPE allowlist), not on terms. The counts above are
the allowlist's starting material. Fields `PUBLICDISPLAY`, `OPENTOPUBLIC`, `SEASONAL` and
`XYACCURACY` exist, so the filter can be strict. Water types are spelled at least six ways, so the
allowlist …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "ArcGIS layer `.../NationalDatasets/NPS_Public_POIs_Geographic/MapServer/0`: 35,639 points, 382 POITYPE"
        " values. Hiker-relevant types: Campsite 3,859; Restroom 2,631; Trailhead 2,211; Campground 863; "
        "Overlook 611; Viewpoint 563; Bridge 476; Ranger Station 279; Vault Toilet 255; Potable Water 214, "
        "Backcountry Campsite 203, Drinking Water 136, Shelter 117, Water 43, Water - Drinking/Potable 34, "
        "Weather Shelter 29, Spring 25, Lookout/Tower 26, Hut 10. Also `NPS_Public_ParkingLots_Geographic` "
        "(6,743) and `NPS_Public_Buildings_Geographic` (29,054). API `/campgrounds`: 665.",
        "Skeptic adds (Measured …",
    ),
    where=("https://nps.gov/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
