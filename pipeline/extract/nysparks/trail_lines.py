"""OPRHP's state-park trails, `NY_State_Parks_Trails/FeatureServer/0`.

16,641 polylines, last edited 2026-09-30 (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc). `Status`, which the registry row declares as
`status_field`, reads Closed on 125 rows and Open on 16,473; it is the only
trail layer in the registry whose status anything reads
(ORG_COVERAGE_SURVEY.md §3e). Not landed, each needing a sources.json row:
OPRHP's Empire State Trail (`EST_Public/FeatureServer`, layer 4 `ESTSegment`,
256 polylines summing to 762.9 mi) and `NYS_Greenways/FeatureServer/0`
(1,177 polylines).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprhp_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
