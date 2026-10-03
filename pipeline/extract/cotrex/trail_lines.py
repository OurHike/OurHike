"""A Boulder County snapshot of COTREX, last edited 2024-08-30: 96,897 lines, re-counted 2026-10-01.

Coverage audit, batch b7_long_trails_states. CPW's own
`CPWAdminData/FeatureServer/15` (83,008 lines, last edited 2026-08-27) is the
steward's current layer (ORG_COVERAGE_SURVEY.md §3d), and CPW publishes two
more copies of it. Pointing `cotrex_trails` at CPW's is a reviewed registry
change, not made here. The `access` column reads `no` on 939 rows and nothing
reads it yet (§3e).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("cotrex_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
