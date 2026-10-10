"""The Nez Perce National Historic Trail's own map: the Forest Service's Google My Map, which fs.usda.gov's
interactive-maps page links, read as its KML export.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `usfs_nez_perce_nht_my_map`: 135 placemarks: 110 auto tour stops (points) and 25 suggested travel and
  adventure routes (lines), keyed on the geometry and `name`.

THE LINES ARE DRIVING ROUTES, not tread: they never route and never draw as a trail (the row's notes).
The Foundation's own legacy My Map (`msid=105417867471941730284.000466baf9e3509d0e06f`) 404s as KML (the
coverage audit, 2026-10-01), and usfs_trails holds only 7 NHT-designated features. Before this the file
was the coverage audit's note, which had read only the first 2,000 bytes of the KML.
"""

from extract._gis_files import gis_file

CLAIMS = ("usfs_nez_perce_nht_my_map",)
RESOURCES = [gis_file(key) for key in CLAIMS]
