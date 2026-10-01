"""ATC's A.T. Communities and the maintaining clubs' sections.

The communities layer is the stalest ATC layer that ships, last edited
2023-06-13 (ORG_COVERAGE_SURVEY.md, batch b1_atc); its rows are the towns
places.json lists, by its registry row's `place_kind`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("communities", "trail_club_sections")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
