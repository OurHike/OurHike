"""NYNJTC's Long Path and Highlands Trail layers, on its own ArcGIS Online org.

`Long_Path_2023/FeatureServer/0` (layer `Long_Path_2025Sep`): 43 polylines,
last edited 2026-08-04. `NYNJTC_HighlandsTrail2021sections/FeatureServer/0`:
12 polylines, last edited 2025-12-04 (coverage audit 2026-10-01, batch
b2_nynjtc). The A.T. miles NYNJTC maintains arrive through ATC's centerline
(atc/trail_lines.py), extracted once there (decision 34). Not landed:
`Long_Path_Shawangunk_Ridge_Trail/FeatureServer/0`, 2 polylines; the audit
found the rest of NYNJTC's network only as 40 PDF maps, and parsing those
would be the scrape SOURCE_SURVEY.md §10 refuses (Reasoned).
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nynjtc_long_path", "nynjtc_highlands_trail")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
