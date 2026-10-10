"""Alaska Trails' statewide trail database, `Alaska_Trail_Database/0`: a 2024 compilation.

1,602 lines, last edited 2024-02-20 (coverage audit 2026-10-01, batch
b7_long_trails_states). Not landed: `AKLT_Trail_Segments_Public/0`, 286 lines
of the organisation's own current work, last edited 2026-09-21, with
`Segment_Condition` (Reroute 4, Construction 2, Reconstruct 2).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("alaska_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
