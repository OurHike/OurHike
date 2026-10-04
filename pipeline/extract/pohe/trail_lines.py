"""The Potomac Heritage Trail Association's 'PHTA Trails' Google My Map, read as its KML export.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `phta_trails_map`: 183 placemarks (127 lines, 56 points), keyed on the geometry and `name`.

PLANNED LINES ARE NOT TOLD APART IN THE FILE: the map's legend separates Existing trail from Future
(planned, advocated), and the KML carries that only as line styles nobody has matched to the legend, so
the row is held. The trail also arrives via nps `nps_trails`, where 0 features carry UNITCODE 'POHE' and
446 carry a TRLALTNAME like 'Potomac Heritage' (the coverage audit, 2026-10-01). Before this the file
was that `via nps` note.
"""

from extract._gis_files import gis_file

CLAIMS = ("phta_trails_map",)
RESOURCES = [gis_file(key) for key in CLAIMS]
