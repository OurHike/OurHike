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
"""

from extract._kinds import arcgis_layer

CLAIMS = ("njdep_fire_danger", "njdep_rx_burn_notifications")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
