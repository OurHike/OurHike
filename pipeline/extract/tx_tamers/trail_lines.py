"""Texas Trail Tamers: the state park trails its crews work on, published by Texas Parks and Wildlife.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `tpwd_state_park_trails`: Texas State Parks trails (TPWD). 3,307 lines, keyed on `GlobalID`.

Guadalupe Mountains is LOADED via nps/'s `nps_trails` (UNITCODE GUMO, 55). Austin's Violet Crown Trail
work sits on the City of Austin PARD's layer, which austin_trail/ extracts once.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("tpwd_state_park_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
