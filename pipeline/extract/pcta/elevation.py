"""PCTA's two elevation classifications of the PCT: the trail and its corridor by 1,000-ft band.

`PCT_Per_Thousand_Ft/FeatureServer/0` is the centerline cut into 14 lines,
one per band, with `PCT_Miles` in each; `PCT_Corridor_Elevation_Ranges/
FeatureServer/0` is the corridor as 14 polygons in the same bands. Both say
they come from a 30 m DEM, coarser than 3DEP's 10 m, so they can check a
profile and never be one. The unit is in each label ("1000−2000 ft"), and 6
centerline vertices read against 3DEP each fell inside their stated band
(measured 2026-10-03; sources.json's `elevation_unit_comment`). Twelve labels
separate the range with a minus sign (U+2212), not a hyphen.

`Trips` rows carry `Gain_ft` and `Loss_ft` (coverage audit 2026-10-01, batch
b7_long_trails_states); that layer is not_available.toml [pcta.suggested_hikes]'s to register.
Nothing reads either table yet, and both rows' `reaches_hikers` is false.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("pcta_per_thousand_ft", "pcta_corridor_elevation_ranges")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
