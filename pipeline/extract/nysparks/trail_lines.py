"""NY State Parks' trail lines: OPRHP's state-park trails, and the Empire State Trail's own lines.

- `oprhp_trails`: OPRHP's state-park trails, `NY_State_Parks_Trails/FeatureServer/0`. 16,641
  polylines, last edited 2026-09-30 (coverage audit 2026-10-01, batch b4_oprhp_mohonk_gatc).
  `Status`, which the registry row declares as `status_field`, reads Closed on 125 rows and Open
  on 16,473; it is the only trail layer in the registry whose status anything reads
  (ORG_COVERAGE_SURVEY.md §3e).
- `oprhp_est_segments`: the Empire State Trail's segments, `EST_Public/FeatureServer/4`
  (ESTSegment), 256 polylines summing to 762.9 mi, 283.9 of them On Road (read live 2026-10-08).
- `oprhp_est_connectors`: the trails that meet it as OPRHP draws them, `EST_Public/FeatureServer/2`
  (ConnectorTrail), 26 polylines, the Appalachian Trail among them.

Decision 54's wave 6 (2026-10-08) added the last two, folding the coverage audit's
`empire-state-trail` candidate into this folder; each row says why it is held. Not extracted from
the same service: ESTLeg (layer 3, 61 lines), the segments dissolved by leg, which would land the
same tread twice, and Splits (layer 0), points dividing one leg from the next. Not landed, needing
a sources.json row: `NYS_Greenways/FeatureServer/0` (1,177 polylines).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("oprhp_trails", "oprhp_est_segments", "oprhp_est_connectors")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
