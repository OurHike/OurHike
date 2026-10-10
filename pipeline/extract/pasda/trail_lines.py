"""DCNR's statewide land trails as PASDA republishes them, `pasda/DCNR/MapServer/5`.

"DCNR Statewide Land Trails 202306": 684 lines (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa). Not landed: DCNR's own
`StateParkTrailsMASTER/MapServer/0` (6,148), `BSP_StateParksTrails/FeatureServer/0`
(1,961) and PASDA's `DCNR2/MapServer/29` (1,256). Which of those three is
the published one is @unvalidated; asking DCNR's Bureau of State Parks GIS
settles it. `pasda/ExplorePAtrails/MapServer/0` holds the same count, 684,
under a 202406 name. A count alone does not make it a copy, so it is not a
SAME_AS note until someone compares the rows. This layer's Rachel Carson
Trail is 37.13 mi against the Rachel Carson Trails Conservancy's own 46.2 mi
(ORG_COVERAGE_SURVEY.md §3d).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("pasda_dcnr_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
