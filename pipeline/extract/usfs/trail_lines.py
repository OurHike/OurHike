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
"""

from extract._kinds import arcgis_layer

CLAIMS = ("usfs_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
