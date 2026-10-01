"""The listing of USGS 3DEP's 1/3 arc-second tiles, as `raw_usgs__3dep_13_current`: every object, never a pixel.

3DEP is a US federal work, public domain (fetch_trail_water.py's source
block). The tiles are Cloud-Optimized GeoTIFFs that the elevation build
streams in place, so what lands is the bucket's own record of each one (key,
size, ETag, LastModified): the manifest a month-to-month change is read
from, and the listing ELT.md plans in place of fetch_elevation.py's per-cell
HEADs. Which cells the trail needs is the corridor's question, answered in
dbt from the lines, not in the request.
"""

from extract._kinds import bucket_listing

TYPE = "elevation"
UNREGISTERED = "a non-registry input: fetch_elevation.py's TILE_URL_TEMPLATE is its one home, and 3DEP has no sources.json row"
RESOURCES = [bucket_listing("3dep_13_current")]
