"""Forest Park Conservancy: Forest Park's trails, published by the City of Portland's Parks & Recreation
and by Oregon Metro's RLIS.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `portland_parks_trails`: Parks Trails, City of Portland open data (Portland Parks & Recreation). 2,558 lines, keyed on geometry.
- `ppr_trails`: PPR_Trails (Portland Parks & Recreation). 2,904 lines, keyed on `GlobalID`.
- `oregon_metro_trails`: Trails, Portland region (Oregon Metro RLIS). 28,834 lines, keyed on geometry + `LENGTH`.

Three datasets of the same ground: the city's open-data Parks Trails, PP&R's own PPR_Trails, and Metro's
regional compilation, which names Forest Park Trail in SHAREDNAME. Deduplication is dbt's.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "portland_parks_trails",
    "ppr_trails",
    "oregon_metro_trails",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
