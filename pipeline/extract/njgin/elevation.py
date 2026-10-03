"""NJDEP's Publicly Accessible High Elevation Points in New Jersey, `FeatureServer/11`: each county's high point.

21 points, the elevation in `ELEVATION` in feet (its alias says "Elevation
(ft)", and 3 points sit a median of 0.47 m from 3DEP; measured 2026-10-03).
Its licence is the NJDEP Data Distribution Agreement, the same text as
`njdep_licence`'s, so the same three conditions travel with it. Nothing reads
it yet, and its `reaches_hikers` is false.

Not landed here, and why (coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa,
not re-read): NJGWS DGS99-4, "Digital Elevation Grids for New Jersey
(1:100,000 scale)", is a raster in a zip, and decision 35 lands no raster;
DGS00-3's 1:100,000 contours are a zip too, a file for decision 54's wave 2,
and contours are the maintainer's call (wave 1 registers none: background-map
material, which decision 35 does not cover). The audit's "hosted trails
layer" whose `grade_max` and `grade_mean` are populated on 270 of 3,068
segments is neither of the two NJ trail layers registered: neither has a
grade, elevation or slope field (read 2026-10-03, 3,305 and 13,296 rows). Which
layer it is was not found; it would be trail_lines.py's to register.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nj_high_elevation_points",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
