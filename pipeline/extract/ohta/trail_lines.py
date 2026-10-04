"""The Ozark Highlands Trail Association's own line, the 'OHTA Website Track' Google My Map, read as its
KML export.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `ohta_website_track`: 5 sections (Boston Mountains, OHT/BRT, Lower Buffalo Bushwhack, Sylamore, Lake
  Norfork), keyed on the geometry.

The map is captioned 'For illustrative purposes only', so it never outranks USFS's line: `usfs_trails`
holds the OZARK HIGHLANDS TRAIL as 16 features, 132.50 mi, and `nps_trails` 3 BUFF features (the
coverage audit, 2026-10-01). Before this the file was that `via usfs` note.
"""

from extract._gis_files import gis_file

CLAIMS = ("ohta_website_track",)
RESOURCES = [gis_file(key) for key in CLAIMS]
