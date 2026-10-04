"""The Hoosier Hikers Council's Tecumseh Trail points, `/assets/Tecumseh_Trail_POI_Waypts.gpx`.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `hhc_tecumseh_waypoints`: 27 waypoints (numbered parking areas, road crossings, a rock shelter and
  Foxes Den Shelter), last modified 2017-10-05, keyed on the geometry. Every `sym` is 'RED MAP PIN', so
  a point's kind is in its name only. Its parking list predates the 2022 reroute (the coverage audit's
  skeptic, 2026-10-01). Not landed: `/assets/Tecumseh_Trail_Guide.pdf` (2022-06-30), which covers
  parking, access, water and camping, a PDF (wave 4).
"""

from extract._gis_files import gis_file

CLAIMS = ("hhc_tecumseh_waypoints",)
RESOURCES = [gis_file(key) for key in CLAIMS]
