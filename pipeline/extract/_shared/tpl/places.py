"""Trust for Public Land: ParkServe's parks, held. Decision 126 (the maintainer's poll, 2026-10-09: "Load it,
held") loads it under decision 122; what it is used for is decided later. TPL keeps its trail_orgs.json row, a
national umbrella with no trail data (extract/_shared/not_clubs.py's line), so this folder is not a club's.

- `tpl_parkserve_parks`: `ParkServe/ParkServe_ProdNew/MapServer/2` on TPL's own ArcGIS Server, 154,780 park
  polygons with public access in 13,913 US places: 1.25 GB as GeoJSON, read whole in 10 minutes and landed as a
  589 MB parquet file (2026-10-09, the row's notes).

Monthly, the type's lane. TPL's server keeps no editing info, so the change check is the statistics fingerprint on
park_dateadded and the summed boundary length (the row's `freshness`); without it the whole layer would be read
every month.
"""

from extract._kinds import arcgis_layer

TYPE = "places"
CLAIMS = ("tpl_parkserve_parks",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
