"""NYC DOT's off-street greenways (`mzxg-pwib`), and two slices of the city's Street Centerline (`inkn-q76z`).

Each read under its registry row's own `where`, measured 2026-10-01: the
current off-street greenways, 3,039 of the bike network's rows; Centerline's
pedestrian ways, 6,496; and the park drives closed to cars, 124. The two
Centerline predicates shared 0 rows that day, so they are two slices of one
dataset rather than two copies (tests/test_extract_layout.py, `upstream`). The
Centerline's own attribution is OTI, not NYC DOT (ORG_COVERAGE_SURVEY.md §3b).
DOT's ArcGIS Online `Bike_Network_Public_View/FeatureServer/0` holds 24,461
polylines and adds `jurisdicti` and `spur` (coverage audit, batch
b5_nyc_nj_ct_ma_pa); its count differs from the Socrata network's, so it is
not shown to be a copy.
"""

from extract._kinds import socrata_dataset

CLAIMS = ("nyc_dot_greenways", "nyc_cscl_paths", "nyc_park_drives")
RESOURCES = [socrata_dataset(key) for key in CLAIMS]
