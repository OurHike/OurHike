"""Finger Lakes Trail Conference: points of interest, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Water and shelters on a 1,000-mi trail OurHike shows as a bare line.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`…/Waypoints/FeatureServer/8`: 1,789 points (lastEdit 2026-06-14). By Category: Parking/Access 865, "
        "PointsOfInterest 354, Camping 164, WaterAndRestrooms 122, TrailJunctions 90, HuntingClosures 76, Map "
        "Info 63, PostOffices 27, PassportHikes 21, Advisory 7. Also `/lean-tos-bivouac-areas-campgrounds/`: an"
        " HTML table of 296 rows (53 lean-tos, 57 bivouacs, 18 public and 13 private campgrounds, facilities, "
        "miles from trail).",
    ),
    where=("https://fingerlakestrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
