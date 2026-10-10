"""OSM's fourteen A.T. state extracts from Geofabrik, kept in the raw store monthly, as `raw_osm__osm_water`.

OpenStreetMap is an aggregator (decision 18), so it lives in _shared/. The
table is the extracts' manifest, one row per state: where the copy is kept
under the monthly lane's `current/osm/`, its size, sha256 and Geofabrik's
Last-Modified. Never the bytes (decision 4), and never the water: the water
points and site water are refresh-reference.yml's pin job's scans of the
copies (fetch_osm_water.py, fetch_trail_water.py --derive), landed in
build-reference.yml's build by step_osm_water.py and step_site_water.py.
extract/_geofabrik.py is the design
and holds the 30-day maximum age (#1652 — Download OSM's Geofabrik extracts
at most once a month, into a private raw bucket that outlives the 7-day
Actions cache).

The licence is ODbL 1.0, quoted on the registry row: attribution and
share-alike. The registry key is `osm_water`, the row the water fetch has
had since 2026-08-13, so the table keeps that name; the basemap's extracts
are the same fourteen files (ELT.md, "The basemap": the one shared piece).
"""

from extract._geofabrik import geofabrik_extracts

TYPE = "points_of_interest"
CLAIMS = ("osm_water",)
RESOURCES = [geofabrik_extracts("osm_water")]
