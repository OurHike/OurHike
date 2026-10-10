"""Bay Area Ridge Trail Council: the Ridge Trail's official route, from the Council's own ArcGIS Online
organization.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `ridgetrail_official_route`: Bay Area Ridge Trail official route, public (Bay Area Ridge Trail Council). 118 lines, keyed on `Segment_ID`.

Not landed: the GPX the Council offers per segment (coverage audit), files for wave 2's reader.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ridgetrail_official_route",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
