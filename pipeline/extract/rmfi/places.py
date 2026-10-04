"""The Rocky Mountain Field Institute's project map, a Google My Map read as its KML export.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `rmfi_project_map`: 46 project sites (Garden of the Gods, Pikes Peak, Red Rock Canyon Open Space …),
  keyed on the geometry. Work sites, which the places mart has no kind for yet; the row says so.
"""

from extract._gis_files import gis_file

CLAIMS = ("rmfi_project_map",)
RESOURCES = [gis_file(key) for key in CLAIMS]
