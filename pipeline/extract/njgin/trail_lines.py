"""NJDEP's two registered trail layers, which are two datasets rather than a copy and its original.

On-prem `Features/Land/MapServer/63`, the state park service's trails, holds
3,305 rows, and `Statewide_Trails_in_New_Jersey/FeatureServer/10` holds 13,296,
last edited 2026-06-09 (coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa).
The on-prem layer is the older of two park-trail layers: NJDEP's hosted
`NJ_State_Park_Service_Trails_h/FeatureServer/63` (3,068 rows, edited
2026-09-02) is the one NJDEP's newest Trail Tracker draws
(ORG_COVERAGE_SURVEY.md §3d). The counts differ, so it is not a SAME_AS copy.
Pointing `njdep_park_trails` at it is a reviewed registry change, not made
here.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("njdep_park_trails", "nj_statewide_trails")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
