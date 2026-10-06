"""The Forest Service's national trail layer, `EDW_TrailNFSPublish_01/MapServer/0`.

86,417 features on 2026-10-01 against 86,329 on 2026-09-02 (coverage audit,
batch b6_federal). Extracted once, here, for every club whose trail it
carries (decision 34); dbt assigns each club its portion. The server is
on-prem, the registry row's ETag stood still while the count moved
(ORG_COVERAGE_SURVEY.md §3b), and the TrailNFS schema has no date column to
declare as `freshness.field`, so the change check answers UNKNOWN and the
layer is read whole every month. Not landed:
`EDW_TrailNFSPublishWithDataStatus_01`, the per-forest map of where the Forest
Service says it has no trail data.

Decision 54, wave 1: read live on 2026-10-03 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests to one host) and registered in sources.json, where each row carries the count, extent,
statistics fingerprint, measured key, person fields and the item's own terms. USFS Region 6 publishes
the Pacific Northwest Trail's congressional route on its own ArcGIS Online organization (owner
USFSRegion06), extracted once here; not_available.toml [pnta.trail_lines] names it. Its own licenseInfo says it 'is not
intended for trip planning', which decision 38 holds against publishing.

- `usfs_pacific_northwest_trail`: Pacific Northwest National Scenic Trail, congressional route as of 2016 (USFS Region 6). 456 lines, keyed on geometry.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "usfs_trails",
    "usfs_pacific_northwest_trail",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
