"""Mohonk Preserve: places, extracted (decision 54, wave 1; live read 2026-10-03 under lib/user_agent.py's
USER_AGENT).

- `mohonk_preserve_boundary`: Mohonk Preserve boundary, 1 polygon feature; places kind `park`.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("mohonk_preserve_boundary",)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
