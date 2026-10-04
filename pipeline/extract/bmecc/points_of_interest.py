"""The Blue Mountain Eagle Climbing Club's trail-section map, a Google My Map read as its KML export: its
shelters, springs, campsites, parking, vistas, access points and the hospitals near the trail.

Decision 54, waves 2 and 3: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or
more between requests to one host) and registered in sources.json, where each row carries the count, the
files' validators, the measured key, the terms and what holds it back.

- `bmecc_trail_section_map`: 111 placemarks (108 points, 3 lines), keyed on the geometry.

A SPRING IS NOT DRINKING WATER here: the 16 springs carry no potability or reliability field, so none
maps to water (the row's notes). The club's shelters page (`/appalachian-trail/shelters`: build year,
water, privy, caretaker, 'sleeps N' for 5 of 8) is an HTML page, wave 5's. bmecc/trail_lines.py and
bmecc/places.py SHARE this resource.
"""

from extract._gis_files import gis_file

CLAIMS = ("bmecc_trail_section_map",)
RESOURCES = [gis_file(key) for key in CLAIMS]
