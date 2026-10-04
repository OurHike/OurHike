"""The Natural Bridge Appalachian Trail Club's point files under home.nbatc.org/MapData/.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `nbatc_trail_features`: 25 bridges, parking areas, summits and crossings (KMZ, 2024-07-23).
- `nbatc_shelters`: 12 shelters (KML, 2013-02-17), which ATC's loaded shelters layer also carries,
  newer.
- `nbatc_trail_info`: 12 hike and feature points (KML, 2013-02-17).

Each keyed on the geometry. None has a type field, so a point's kind is in its name only, which the POI
mart never reads one from.
"""

from extract._gis_files import gis_file

CLAIMS = ("nbatc_trail_features", "nbatc_shelters", "nbatc_trail_info")
RESOURCES = [gis_file(key) for key in CLAIMS]
