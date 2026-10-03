"""MassGIS's long-distance trails, `AGOL/Long_Distance_Trails/MapServer/0`.

32 lines under 7 names, no `editingInfo` (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa). The steward is DCR, and the lines are compiled from club
GPS tracks (ORG_COVERAGE_SURVEY.md §3b). Not landed: `AGOL/Map_Trails_Pub_True/FeatureServer/0` (9,553
trail segments compiled by the regional planning agencies, coverage audit), which the audit names by its
path in arcgisserver.digital.mass.gov's AGOL folder, and which was not read, for the robots.txt answer
below.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms. DCR's own statewide roads
and trails layer is extracted here too, from the Energy and Environmental Affairs ArcGIS Online
organization. MassGIS's layer of the same name and count, `AGOL/DCR_Roads_and_Trails_Arcs` (36,859,
coverage audit), sits on arcgisserver.digital.mass.gov, whose robots.txt answered 502 twice on
2026-10-03, which RFC 9309 reads as a full disallow, so it was not read or compared.

- `dcr_roads_and_trails`: DCR Roads and Trails, statewide (MA DCR). 36,859 lines, keyed on `GlobalID`.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "massgis_long_distance_trails",
    "dcr_roads_and_trails",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
