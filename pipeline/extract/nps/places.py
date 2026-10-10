"""National Park Service: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `nps_park_boundaries`: NPS Boundary (Land Resources Division), 442 polygon features; places kind
  `park`.
- `nps_legislated_wilderness`: NPS Legislated Wilderness, 61 polygon features; places kind `park`.
- `grsm_municipal_boundaries`: Great Smoky Mountains gateway municipal boundaries (GRSM), 22 polygon
  features; places kind `town`.
- `grsm_park_boundary_lines`: Great Smoky Mountains park boundary lines (GRSM), 19 polyline features; no
  places kind.
- `pohe_trail_regions`: Potomac Heritage NST management regions (POHE), 9 polygon features; no places
  kind.

Not registered: layers 0 (boundary centroids) and 1 (tracts) of the boundary service.

Decision 54, wave 3 (2026-10-04): `nps_api_places`, the NPS Data API's /places, 17,505 nationally by
the API's own total (one request with api.data.gov's public demo key). It needs NPS_API_KEY, which the
monthly job does not pass yet, so until a maintainer adds it the table is withdrawn as unavailable,
never read as empty (extract/_ogc.py's JsonFeatures). One extraction for every club whose places the
NPS lists (decision 34): each draws its portion by `relatedParks` in dbt.
"""

from extract._kinds import arcgis_layer
from extract._ogc import json_features

CLAIMS = (
    "nps_park_boundaries",
    "nps_legislated_wilderness",
    "grsm_municipal_boundaries",
    "grsm_park_boundary_lines",
    "pohe_trail_regions",
    "nps_api_places",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS[:-1]] + [json_features("nps_api_places")]
