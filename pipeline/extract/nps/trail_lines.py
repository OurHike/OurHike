"""The Park Service's national trail layer, `NPS_Public_Trails/FeatureServer/0`.

31,484 features on 2026-10-01, against the registry's 31,485 on 2026-09-30
(coverage audit, batch b6_federal). `max(EDITDATE)` read 2026-09-30, a real
change marker, but the registry row declares no `freshness.field`, so the
change check answers UNKNOWN and the layer is read whole; declaring
`freshness.field: EDITDATE` would let unchanged months skip. `TRLSTATUS` marks
60 rows Temporarily Closed and 20 Decommissioned, and nothing reads it yet
(ORG_COVERAGE_SURVEY.md §3e).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nps_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
