"""The Blue Mountain Eagle Climbing Club's trail-section map, a Google My Map read as its KML export: its
shelters, springs, campsites, parking, vistas, access points and the hospitals near the trail.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `bmecc_trail_section_map`: 111 placemarks (108 points, 3 lines), keyed on the geometry.

A SPRING IS NOT DRINKING WATER here: the 16 springs carry no potability or reliability field, so none
maps to water (the row's notes). not_available.toml [bmecc.trail_lines] and not_available.toml [bmecc.places] SHARE this resource.

NOT LANDED, read live 2026-10-04 for decision 54's wave 5 (no robots.txt on www.bmecc.org: 404, no rules):
the club's shelters page, https://www.bmecc.org/appalachian-trail/shelters, 8 A.T. shelters south to north,
each in prose (build year, water, privy, caretaker, 'Sleeps 6' on 4) with no coordinate and only a distance
from a road ('9.1 miles south of Port Clinton'). ATC's layers place the same shelters, so its facts need a join
to those points by name, which a person reviews; needs a per-site reader, not built in this pull request. A
HIKER'S SAFETY: the page says the Route 501 Shelter "was retired in November of 2025. NO Camping is permitted in
or around the 501 Shelter!" ("Closed by the NPS"), while ATC's shelters layer (ANST_Facilities/FeatureServer/4,
loaded as `shelters`) still lists '501 Shelter' as 'Official A.T. Shelter' (read 2026-10-04).
"""

from extract._gis_files import gis_file

CLAIMS = ("bmecc_trail_section_map",)
RESOURCES = [gis_file(key) for key in CLAIMS]
