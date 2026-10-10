"""The NC High Peaks Trail Association's trail lines, the KML its interactive map loads
(`/interactivemaps/TrailSunday3.xml`).

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `nchpta_trails`: 28 lines (USFS trails 161 to 201, Mount Mitchell State Park's trails and 4 MST
  pieces), last modified 2023-02-08, keyed on the geometry.

The site's footer reads 'Copyright 2026- All Rights Reserved', which decision 37 reads past for a layer
on a public endpoint; the words are quoted on the row. The numbered USFS trails are likely also in
`usfs_trails` and the MST pieces in `nc_mst_trail` (Reasoned); dbt deduplicates.
"""

from extract._gis_files import gis_file

CLAIMS = ("nchpta_trails",)
RESOURCES = [gis_file(key) for key in CLAIMS]
