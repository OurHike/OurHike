"""NCTA's North Country Trail, `nct_public/FeatureServer/2`.

4,004 lines, last edited 2026-04-24 (coverage audit 2026-10-01, batch
b7_long_trails_states). Its `closure` column (Closed 4, Highwater 2, Hunting
2) is read by nothing yet (ORG_COVERAGE_SURVEY.md §3e). Not landed: the 14 "new route" lines in
`trail_alerts/FeatureServer/2`.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms. NCTA's other public trail
layers on its own organization, each an independent dataset. agol_sht_public and agol_flt are not
copies of `nct_public/FeatureServer/2` (compared 2026-10-03 on seg_id and on every shared column);
trls_other's spurs and nearby trails are, by their layers' own names, lines the main layer does not
hold, and were not compared row by row.

- `ncta_spurs`: North Country Trail spurs (NCTA). 304 lines, keyed on geometry.
- `ncta_nearby_trails`: Trails near the North Country Trail (NCTA). 2,243 lines, keyed on geometry + `seg_name` + `updated`.
- `ncta_superior_hiking_trail`: Superior Hiking Trail, NCTA's public layer (agol_sht_public). 272 lines, keyed on geometry.
- `ncta_finger_lakes_trail`: North Country Trail segments of the Finger Lakes Trail (NCTA, agol_flt). 417 lines, keyed on geometry.

trail_orgs.json calls NCTA's endpoint `ogc_features`, and no OGC resource is written (decision 54, wave 3, read
2026-10-04). https://gis.northcountrytrail.org/ is an ArcGIS Hub site over this same organization (orgId
UfGVyqUm4GHa2zrj; its robots.txt asks `Crawl-delay: 60`), offering "CSV, KML, Zip, GeoJSON" downloads and "API links
for GeoServices, WMS, and WFS" of its items; the organization's services directory lists 69 FeatureServers and no
OGCFeatureServer or WFSServer. So the hub's formats are views of the layers above, the same data, and
extract/_ogc.py's ogc_features kind waits for a publisher whose OGC API Features collection is its own.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "ncta_trail",
    "ncta_spurs",
    "ncta_nearby_trails",
    "ncta_superior_hiking_trail",
    "ncta_finger_lakes_trail",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
