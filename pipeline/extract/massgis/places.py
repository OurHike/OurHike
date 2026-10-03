"""MassGIS (Bureau of Geographic Information): places, extracted (decision 54, wave 1; live read 2026-10-03
under lib/user_agent.py's USER_AGENT).

- `massgis_openspace`: Protected and Recreational OpenSpace (Polygons), 61,486 polygon features; places
  kind `park`.

AGOL/Census2020_Towns is the Census's boundaries and is not registered.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("massgis_openspace",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
