"""NJDEP / NJGIN — Statewide Trails: warnings, 2 ArcGIS layers extracted here (decision 53 phase B,
2026-10-03).

- `njdep_fire_danger`: NJ Forest Fire Service wildfire danger by division,
  `Envr_admin_FFS_danger_public/FeatureServer/2`.
- `njdep_rx_burn_notifications`: NJ Forest Fire Service prescribed burn notifications,
  `Envr_admin_FFS_RxB_app_pts_public/FeatureServer/0`.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

NJDEP / NJGIN — Statewide Trails: warnings, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

Fire danger plus the campfire-restriction flag is the find: machine-readable, daily, statewide, and
the Forest Fire Service's own. The hunting zones carry no season dates, so they say "hunting happens
here", not "this week". The prescribed-burn layer is the right shape for "smoke ahead" when it has …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `Envr_admin_FFS_danger_public/FeatureServer/2` "NJ Wildfire
Danger Level": 3 Forest Fire Service division polygons, with `FIRE_DANGER` (sample: Northern NJ
"LOW"), `RECFIRE_RESTRICTION` (the campfire restriction flag), `KBDI` and `BUILDUP`. Edited
2026-09-30 10:55 UTC, which is consistent with a daily update. `Envr_admin_FFS_RxB_app_pts_public/0`
Prescribed Burn Notification Locations: 0 rows today, edited 2026-09-17. WMA Restrictions
"Restricted Use" 186 (No Hunting 158, Archery Only 17, …). Hunting layers: `Turkey_Hunting_Areas`
(18), `Black_Bear_Management_Zones/160` (7, edited …

Its `where`:
https://services1.arcgis.com/QWdNfRs7lkPq4g4Q/arcgis/rest/services/Envr_admin_FFS_danger_public/FeatureServer/2
https://mapsdep.nj.gov/arcgis/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import arcgis_layer

CLAIMS = ("njdep_fire_danger", "njdep_rx_burn_notifications")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
