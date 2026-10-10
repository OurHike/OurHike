"""TRTA's trail system, `TRT_System_Fixed/FeatureServer/0`.

132 lines, last edited 2026-06-04 (coverage audit 2026-10-01, batch
b7_long_trails_states). `Tahoe_Rim_Trail_System_view/0` also holds 132 lines
and was last edited 2026-09-30; the same count with a later edit is not
shown to be the same data, so it is not a SAME_AS note until someone
compares the rows. Not landed: `Other_Trails/0` (752 connectors) and
`Use_Restrictions/0` (104 lines with an `availability` code that reads as
hike/horse/bike, @unvalidated until TRTA's legend settles it).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("tahoe_rim_trail",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
