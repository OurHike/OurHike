"""The Catamount Trail Association's places, from its interactive map's data files.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `catamount_sections`: the trail's 31 numbered sections (GeoJSON polygons, 2017-11-27).
- `catamount_businesses`: 77 lodging, food, Nordic and alpine businesses (CSV with LATITUDE and
  LONGITUDE, 2017).
- `catamount_backcountry_zones`: 6 backcountry ski zones (CSV, 2017).

Each keyed on the geometry. Not landed: the `/bc-zones/` pages, HTML (wave 5).
"""

from extract._gis_files import gis_file

CLAIMS = ("catamount_sections", "catamount_businesses", "catamount_backcountry_zones")
RESOURCES = [gis_file(key) for key in CLAIMS]
