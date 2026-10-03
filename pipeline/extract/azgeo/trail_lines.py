"""The Arizona Trail Association's connector trails, layer 5 of `Arizona_National_Scenic_Trail_Feature_Layers_view`.

145 lines, 228.9 mi (coverage audit 2026-10-01, batch b7_long_trails_states).
The trail itself is layer 3 (44 passages, 831.6 mi, last edited 2026-09-04)
and is not registered, so today the main line reaches a hiker only where
`usfs_trails` carries it (ORG_COVERAGE_SURVEY.md §3b). The layers sit in the
Arizona Trail Association's own org, so the registry row's `steward` and its
state-publication licence argument are wrong too. Both are reviewed registry
changes, not made here; this folder extracts the row as it stands.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("azgeo_arizona_trail",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
