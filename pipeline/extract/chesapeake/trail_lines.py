"""Chesapeake Conservancy: the Captain John Smith Chesapeake NHT's water trail and a baywide trails
compilation, from the Conservancy's own ArcGIS Server (cicgis.org).

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `chesapeake_cajo_complete`: Captain John Smith Chesapeake NHT water trail, CAJO_Complete (Chesapeake Conservancy). 843 lines, keyed on geometry.
- `chesapeake_baywide_trails`: Baywide Trails compilation (Chesapeake Conservancy). 23,146 lines, keyed on geometry + every attribute column.

NPS's own centerline of the same NHT is nps/'s `nps_captain_john_smith_nht` (832 lines), an independent
line of the same water. CAJO_Complete's server refuses pagination, and the extract reads it by object id
(its row's pagination_comment).
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "chesapeake_cajo_complete",
    "chesapeake_baywide_trails",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
