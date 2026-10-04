"""Friends of the Mountains-to-Sea Trail's primary trailheads, the "Primary Trailheads" Google Sheet, read as
its CSV export.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first on docs.google.com and on the
googleusercontent.com host its export redirects to, lib/user_agent.py's agent, 2 s or more between
requests to one host) and registered in sources.json, where the row carries the count, the validators,
the measured key, the sheet's own terms and what holds it back. The coverage audit filed it as a web
page; it is a CSV of points, so it is a `gis_file` with a `header_row`, because the sheet's first line
is its note and its date.

- `fmst_primary_trailheads`: 264 trailheads, keyed on the geometry.
"""

from extract._gis_files import gis_file

CLAIMS = ("fmst_primary_trailheads",)
RESOURCES = [gis_file(key) for key in CLAIMS]
