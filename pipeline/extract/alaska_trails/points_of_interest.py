"""Alaska Trails: points of interest, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

The 26 `Proposed` access points must not render as real.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`AccessPoints/FeatureServer/12`: 183 (157 `Exists`, 26 `Proposed`), with `Camping`, `ParkingLot`, "
        "`Toilet`, `Fee`; last edit 2026-05-08. `AKLT_Cabins_and_Campsites/10`: 108 (Campground 53, "
        'Cabin/Hut/Yurt 29, Campsite(s) 26), labelled "Draft layer". Regional Access Points and Camping '
        "Infrastructure services exist for Seward–Girdwood, Anchorage, Eagle River–Cantwell, Denali and "
        "Fairbanks.",
    ),
    where=("https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services/AccessPoints/FeatureServer/12",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
