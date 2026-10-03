"""Friends of the Blue Hills: the Blue Hills Reservation's trail lines, published by the landowner,
Massachusetts DCR.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms.

- `dcr_blue_hills_trails`: Blue Hills Reservation trail lines (MA DCR, public). 1,630 lines, keyed on `GlobalID`.

DCR's statewide roads and trails layer, which carries the same reservation among every DCR property, is
massgis/'s; the two are independent datasets of the same ground. FBH's own maps are PDFs of DCR's map
(coverage audit), a format no reader takes yet.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("dcr_blue_hills_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
