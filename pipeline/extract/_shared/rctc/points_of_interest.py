"""Rachel Carson Trails Conservancy: points of interest, held. A candidate steward with no trail_orgs.json row yet, so
it lives in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every
type, held"). Held until the maintainer approves the conservancy's trail_orgs.json row in chat (decision 121); then
this file moves to the club folder of the same name.

- `rctc_baker_trail_geojson`: the Baker Trail's GeoJSON (/gis/bt-geojson, which redirects to a dated file), 106
  features on 2026-10-09: 8 shelters, 24 parking areas and 3 campgrounds among its 35 points, and the route and its
  spurs as 71 lines. Its HEAD carries no validator of the file's own, so it is read whole each month (259 KB).

The Rachel Carson Trail's own file holds no shelter or water, and waits with the conservancy's other layers. Raw only
until the steward has a folder of its own. Monthly.
"""

from extract._gis_files import gis_file

TYPE = "points_of_interest"
CLAIMS = ("rctc_baker_trail_geojson",)
RESOURCES = [gis_file(key) for key in CLAIMS]
