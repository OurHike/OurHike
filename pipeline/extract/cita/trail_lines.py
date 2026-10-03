"""Central Iowa Trail Association: the trails its areas sit in, published by the City of Des Moines for the
regional GIS partnership and by Iowa DNR.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `des_moines_trails`: Trails, Des Moines Area Regional GIS (City of Des Moines). 4,924 lines, keyed on `GlobalID`.
- `iowa_dnr_state_park_trails`: Iowa state park and state forest trails (Iowa DNR). 2,386 lines, keyed on `GlobalID`.

CITA's own areas (Ewing Park, Sycamore, Center and Denmans and others) are segments of the Des Moines
layer by name (coverage audit, 2026-10-01). Not landed: the Johnston layer the audit's trimmed note
names, which was not identified in this read.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "des_moines_trails",
    "iowa_dnr_state_park_trails",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
