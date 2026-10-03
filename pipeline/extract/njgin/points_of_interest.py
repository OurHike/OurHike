"""NJDEP / NJGIN — Statewide Trails: points of interest, published, and not landed (coverage audit
2026-10-01, batch b5_nyc_nj_ct_ma_pa).

Water is the safety trap. Of the 17 water points, 4 are named "Potable Water NOTE NonFunctional":
the status lives in the name. A loader must exclude these by an allowlist on name and type, as
`nyc_drinking_fountains` does, and ship the rest at a reduced confidence rather than the default.
The 524 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://mapsdep.nj.gov/arcgis/rest/services/Features/Land/MapServer/62` (hosted twin "
        "`Open_Space__State_Owned__Points_of_Interest_h/FeatureServer/62`, edited 2026-06-23): 3,260 points. "
        "`FEATURE_TYPE` includes Parking 463, Unpaved Parking 373, Pulloff Parking 202, Scenic View 163, "
        "Restroom 142, Trailhead 138, Bridge 132, Campground 47, Cabins 30, Group Campground 25, Shelter 17 (3 "
        'named "AT … Shelter": High Point, Mashipacong, Rutherford), Water 17, Lean To 14 (all at Meisle '
        'Campground), First Aid 6 and Fire Tower 4. `OPNS_STAT` carries seasons ("April 1 to Oct 31" 45, '
        '"Seasonal" 77). …',
    ),
    where=(
        "https://mapsdep.nj.gov/arcgis/rest/services/Features/Land/MapServer/62",
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/Open_Space__State_Owned__Points_of_Interest_h/FeatureServer/62",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
