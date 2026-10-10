"""The Bartram Trail Conference's two Google My Maps, read as their KML exports.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `bartram_trail_markers_map`: 'Bartram Trail Markers', 127 placemarks: 88 historical markers, 38 lines
  and a polygon, keyed on the geometry.
- `bartram_trail_map`: 'Bartram Trail', 245 placemarks: sites, markers (35 with no geometry), properties
  and the routes of William and John Bartram's travels and the Federal Road, keyed on the geometry and
  `description`.

Every line is a historic route, never tread, and never routes or draws as a trail (the rows' notes).
"""

from extract._gis_files import gis_file

CLAIMS = ("bartram_trail_markers_map", "bartram_trail_map")
RESOURCES = [gis_file(key) for key in CLAIMS]
