"""NCTA's North Country Trail, `nct_public/FeatureServer/2`.

4,004 lines, last edited 2026-04-24 (coverage audit 2026-10-01, batch
b7_long_trails_states). Its `closure` column (Closed 4, Highwater 2, Hunting
2) is read by nothing yet (ORG_COVERAGE_SURVEY.md §3e). Not landed:
`trls_other/FeatureServer/2`, 304 spurs, and the 14 "new route" lines in
`trail_alerts/FeatureServer/2`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ncta_trail",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
