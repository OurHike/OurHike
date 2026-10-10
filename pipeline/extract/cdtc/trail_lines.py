"""The 2016 Wyoming GISC copy of the CDT, `CDTrailCoalition/MapServer/0` on services.wygisc.org.

Coverage audit 2026-10-01, batch b7_long_trails_states. CDTC's own
`Continental_Divide_Trail_2/FeatureServer/0` (7 lines, 3,074.5 mi, last
edited 2026-09-30, CC BY) is the current layer (ORG_COVERAGE_SURVEY.md §3d).
Pointing `cdtc_centerline` at it is a reviewed registry change, not made
here.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("cdtc_centerline",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
