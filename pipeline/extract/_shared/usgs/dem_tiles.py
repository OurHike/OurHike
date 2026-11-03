"""The listing of USGS 3DEP's 1/3 arc-second tiles, as `raw_usgs__tnm_3dep_13_current`: every object, never a pixel.

3DEP is a US federal work, public domain (fetch_trail_water.py's source
block). The tiles are Cloud-Optimized GeoTIFFs that the elevation build
streams in place, so what lands is the bucket's own record of each one (key,
size, ETag, LastModified): the manifest a month-to-month change is read
from, and the listing ELT.md plans in place of fetch_elevation.py's per-cell
HEADs. Which cells the trail needs is the corridor's question, answered in
dbt from the lines, not in the request.

The key is `tnm_3dep_13_current`, after The National Map's `prd-tnm` bucket
it lists, and not `3dep_13_current`: dlt escapes a name segment that starts
with a digit, so that key landed as `raw_usgs___3dep_13_current` while the
run check counted `raw_usgs__3dep_13_current`, and refused the monthly lane
for an empty elevation table it had in fact loaded (run 37058045092,
2026-10-02). extract/_contract.py's raw_table() now refuses such a key.
"""

from extract._kinds import bucket_listing

TYPE = "elevation"
UNREGISTERED = "a non-registry input: fetch_elevation.py's TILE_URL_TEMPLATE is its one home, and 3DEP has no sources.json row"
RESOURCES = [bucket_listing("tnm_3dep_13_current")]
