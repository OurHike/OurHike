"""NCTA's Kekekabic Trail mileage index, `kek_mileage_elev/FeatureServer/0`: 394 points every 0.1 mile, each with an elevation.

A mileage-elevation series of the kind that calibrates a 3DEP profile: one
point per tenth of a mile along the Kekekabic section in Minnesota, its
elevation in the attribute `Z` (the geometry has none, hasZ false), in FEET.
The layer names no unit; 5 points read against 3DEP sit a median of 0.65 m
away as feet and 1,215 m away as metres (measured 2026-10-03; sources.json's
`elevation_unit_comment`). A model that read it as metres would put the
section 3.28 times too high.

STALE, and said so on its row: last edited 2021-01-12, and the service calls
itself a "Temporary Mileage Index". Whether it still matches the tread is
unknown, so it is a check on a profile, not a profile. Nothing reads it yet,
and its `reaches_hikers` is false.

`trls_other`'s `Max_Slope` and `Avg_Slope` (coverage audit 2026-10-01, batch
b7_long_trails_states) are slope attributes on a trail-line layer, which is
trail_lines.py's to register, not elevation.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("ncta_kek_mileage_elev",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
