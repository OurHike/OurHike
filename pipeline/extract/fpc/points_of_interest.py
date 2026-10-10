"""Forest Park Conservancy's trailheads, the Google My Map embedded on /forest-park/maps/, read as its KML
export.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `fpc_forest_park_trailheads`: 19 trailheads, keyed on the geometry.
"""

from extract._gis_files import gis_file

CLAIMS = ("fpc_forest_park_trailheads",)
RESOURCES = [gis_file(key) for key in CLAIMS]
