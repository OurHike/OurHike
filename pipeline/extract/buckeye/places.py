"""Buckeye Trail Association: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `buckeye_retail_map_outlines`: Buckeye Trail retail map outlines, 26 polygon features; no places kind.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("buckeye_retail_map_outlines",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
