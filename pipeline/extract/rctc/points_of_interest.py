"""Rachel Carson Trails Conservancy: points of interest (decision 122's held load, here since the conservancy's row;
closures.py says how this folder came to be).

- `rctc_baker_trail_geojson`: the Baker Trail's GeoJSON (/gis/bt-geojson, which redirects to a dated file), 106
  features on 2026-10-09: 8 shelters, 24 parking areas and 3 campgrounds among its 35 points, and the route and its
  spurs as 71 lines. Its HEAD carries no validator of the file's own, so it is read whole each month (259 KB).

The Rachel Carson Trail's own file holds no shelter or water, and waits with the conservancy's other layers.
make_dbt_staging.py stages these features now that the steward has a folder of its own; no seeds/club_poi_types.csv
row types them yet, so none of them publishes until one does, and no trail_lines file shares the resource, so the
route and spurs draw nothing. Monthly.
"""

from extract._gis_files import gis_file

CLAIMS = ("rctc_baker_trail_geojson",)
RESOURCES = [gis_file(key) for key in CLAIMS]
