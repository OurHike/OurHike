"""The Natural Bridge Appalachian Trail Club's own trail lines, `NBATC_Trails_015.kml` under
home.nbatc.org/MapData/.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `nbatc_trails`: 49 A.T. and side-trail lines, last modified 2016-05-19, keyed on the geometry.

The club's portion of ATC's centerline and side trails is drawn in dbt as before (atc
`centerline`/`side_trails`; 10 of the 20 blue-blazers match a side-trail name, the coverage audit). This
file is the club's own GPS lines beside them, deduplicated after the load. Not landed: the 2013
relocation KMLs and `AT--MD-VA.kmz`, which nobody has read.
"""

from extract._gis_files import gis_file

CLAIMS = ("nbatc_trails",)
RESOURCES = [gis_file(key) for key in CLAIMS]
