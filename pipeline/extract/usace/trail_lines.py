"""U.S. Army Corps of Engineers: two districts' recreational trail layers, Mobile's at Lake Lanier and
Tulsa's.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `usace_mobile_trails`: Recreational trails, Mobile District at Lake Lanier (USACE). 149 lines, keyed on `GlobalID`.
- `usace_tulsa_trails`: Recreation trails, Tulsa District (USACE). 6 lines, keyed on `GlobalID`.

Nothing national: RIDB carries no centerlines (coverage audit). Other districts' layers were not
searched for in this read.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "usace_mobile_trails",
    "usace_tulsa_trails",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
