"""Sierra Buttes Trail Stewardship: the trails it maintains under agreement with the Forest Service.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `sbts_maintained`: SBTS Maintained trails (Sierra Buttes Trail Stewardship). 565 lines, keyed on geometry + `Forest`.

Not landed: the Connected Communities route alternative as GPX and KMZ zips on sierratrails.org
(coverage audit), files for wave 2's reader.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("sbts_maintained",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
