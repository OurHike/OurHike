"""Cumberland Trail / Tennessee State Parks: points of interest, published, and not landed (coverage
audit 2026-10-01, batch c9_federal_state_rest).

For the CT itself, the trail's own CTSST service is richer than TDEC's statewide assets. No water
points found anywhere.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../Public_Hiking_Assets_TN_State_Parks/FeatureServer/0`: 1,369 points: Parking 415, Trailhead 349, "
        "Trail Bridge 183, Campsite-Backcountry 156, Campsite-Walk-In 56, Scenic Viewpoint/Overlook 53, "
        "Campsite-Backcountry Shelter 10, Lookout Tower 5, Suspension Bridge 5. Edited 2026-09-29. Of these, "
        "the CT park holds 4. `.../TN_State_Parks_Campsites`: 3,242, of which 20 are CT. CTSST service: "
        "Campsites (9) 17, Trailheads (1) 46 (edited 2026-08-25), Natural Features (5) 92 (named rocks and "
        "overlooks).",
        'Skeptic adds: `.../TSP_Campground_Point/FeatureServer/1` ("Tennessee State Parks Campground …',
    ),
    where=("https://tnstateparks.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
