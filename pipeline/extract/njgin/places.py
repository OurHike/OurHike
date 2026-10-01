"""NJDEP / NJGIN — Statewide Trails: places, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

The 373 generalized state units are the "which park am I in" layer.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Open_Space__State_Owned__Generalized_h/67`: 373 polygons (edited 2026-07-01). `Open_Space/66`: 95,032"
        " (all owners, edited 2026-07-22). `State_Natural_Areas_Preserve_Boundaries_in_New_Jersey/7`: 47. "
        "`Features/Land/MapServer/5` Parks: 394 points. `Features/Land/MapServer/6` Place Names: 2,641 points "
        "with `FEATURE_CLASS` and `ELEV_IN_FT`. `Land/81` Hidden Gems: 71.",
    ),
    where=(
        "https://mapsdep.nj.gov/arcgis/rest/services/Features/Land/MapServer/5",
        "https://mapsdep.nj.gov/arcgis/rest/services/Features/Land/MapServer/6",
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
