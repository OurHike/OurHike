"""The Ozark Trail Association's map, the Google My Map embedded on ozarktrail.com/maps/, read as its KML
export.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `ota_trail_map`: 161 placemarks: 89 lines (Main Trail 18, Connecting Trail 38, Trailhead Spur 24, OT
  Spur Trail 4, Alternate Trail 2, Road - White 2, Nearby trail 1) and 72 trailheads, keyed on the
  geometry.

The site's terms restrict reproduction (`terms` on the row), which no decision names, so the row is held
for the maintainer. Not landed: the 14 per-section 'GPS Download' zips, which nobody has compared with
this map.
"""

from extract._gis_files import gis_file

CLAIMS = ("ota_trail_map",)
RESOURCES = [gis_file(key) for key in CLAIMS]
