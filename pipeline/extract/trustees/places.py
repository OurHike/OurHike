"""The Trustees of Reservations: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `trustees_properties`: Trustees Properties, 137 polygon features; places kind `park`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("trustees_properties",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
