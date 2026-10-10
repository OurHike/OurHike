"""The Condor Trail Association's 2020 alignment, its four county KMLs under condortrail.com/wp-
content/uploads/kml/.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `condor_trail_2020`: 154 placemarks from 4 files (Ventura 31, Santa Barbara 36, San Luis Obispo 28,
  Monterey 59), all last modified 2021-07-29, keyed on the geometry.

Not loaded via `usfs`: the coverage audit's 2 USFS name matches are other trails. ArcGIS has only a
third-party advocacy layer, `ForestWatchGIS` `CCHPA_Condor_Trail`, 1 polyline drawn for a legislative
map.
"""

from extract._gis_files import gis_file

CLAIMS = ("condor_trail_2020",)
RESOURCES = [gis_file(key) for key in CLAIMS]
