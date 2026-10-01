"""Ice Age Trail Alliance: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

`IAT_Potable_Water` and `IAT_Possible_Water` are views of the same 423 rows. Use the base layer and
the `Potability` code, not the view names. The item says water "is not comprehensive". That is a
per-source coverage caveat the card has to carry. Skeptic: spot-checked `IAT_Water/0` = 423, last
edit …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`.../IAT_Water/FeatureServer/0`: 423 water points. Potability: Potable 198, Treatment required 217, No"
        " water 7, Unknown 1. Type: river/stream 207, drinking fountain 103, water pump 97, lake 7, spring 3, "
        "artesian well 3. Reliability: permanent 62, intermittent/seasonal 86, unknown 274. Last edit "
        "2026-03-31. `.../IAT_Camping1/FeatureServer/0`: 247 camping points: Private 77, Public 66, Dispersed "
        "Camping Area 39, Primitive 33, Public Group 18, Shelter/Hut 12, Cabin 2, with `Water`, `Toilet` and "
        "`Num_Sites`. `.../IAT_Parking/FeatureServer/0`: 443, of which 114 have `Overnight_Park` = Yes. …",
    ),
    where=(
        "https://dnrmaps.wi.gov/arcgis/rest/services",
        "https://iceagetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
