"""Oregon Natural Desert Association: the Oregon Desert Trail's 28 tracks, ONDA's own public ArcGIS layer
`ODT Tracks`.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `onda_odt_tracks`: ODT Tracks, the Oregon Desert Trail's sections (ONDA). 28 lines, keyed on geometry.

Extracted under decision 39: a club's own public ArcGIS layer counts as published whatever its website's
waiver says. ONDA is a refuse row, so rule 7 keeps this off phones until its permission is recorded (its
sources.json row says so). Not fetched: the GPX behind ONDA's waiver form, and Oregon State Parks'
'Oregon Desert Trail' copy (item c851af0d384a4dfc9cf470993339a81c), an agency's copy of a steward's
gated route, which is the maintainer's call.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("onda_odt_tracks",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
