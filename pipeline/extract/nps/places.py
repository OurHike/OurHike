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

Not registered: layers 0 (boundary centroids) and 1 (tracts) of the boundary service. The NPS API's
/places needs a key and waits for wave 3.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "nps_park_boundaries",
    "nps_legislated_wilderness",
    "grsm_municipal_boundaries",
    "grsm_park_boundary_lines",
    "pohe_trail_regions",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
