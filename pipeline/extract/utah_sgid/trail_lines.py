"""UGRC's SGID Trails and Pathways, `TrailsAndPathways/0`.

48,132 lines, last edited 2026-09-18 (coverage audit 2026-10-01, batch
b7_long_trails_states). `Status` reads CLOSED on 122 rows and PROPOSED on 984,
and nothing reads it yet (ORG_COVERAGE_SURVEY.md §3e).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("utah_sgid_trails",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
