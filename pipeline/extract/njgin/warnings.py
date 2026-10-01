"""NJDEP / NJGIN — Statewide Trails: warnings, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

Fire danger plus the campfire-restriction flag is the find: machine-readable, daily, statewide, and
the Forest Fire Service's own. The hunting zones carry no season dates, so they say "hunting happens
here", not "this week". The prescribed-burn layer is the right shape for "smoke ahead" when it has …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`Envr_admin_FFS_danger_public/FeatureServer/2` "NJ Wildfire Danger Level": 3 Forest Fire Service '
        'division polygons, with `FIRE_DANGER` (sample: Northern NJ "LOW"), `RECFIRE_RESTRICTION` (the campfire'
        " restriction flag), `KBDI` and `BUILDUP`. Edited 2026-09-30 10:55 UTC, which is consistent with a "
        "daily update. `Envr_admin_FFS_RxB_app_pts_public/0` Prescribed Burn Notification Locations: 0 rows "
        'today, edited 2026-09-17. WMA Restrictions "Restricted Use" 186 (No Hunting 158, Archery Only 17, …). '
        "Hunting layers: `Turkey_Hunting_Areas` (18), `Black_Bear_Management_Zones/160` (7, edited …",
    ),
    where=(
        "https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/Envr_admin_FFS_danger_public/FeatureServer/2",
        "https://mapsdep.nj.gov/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
