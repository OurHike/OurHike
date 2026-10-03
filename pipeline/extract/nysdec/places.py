"""New York State Dept of Environmental Conservation: places, extracted (decision 54, wave 1; live read
2026-10-03 under lib/user_agent.py's USER_AGENT).

- `dec_lands`: DEC Lands (state land units), 3,234 polygon features; places kind `park`.
- `dec_conservation_easements`: DEC Conservation Easements, 93 polygon features; places kind `park`.
- `dec_wildlife_management_areas`: DEC Wildlife Management Areas, 132 polygon features; places kind
  `park`.
- `dec_adirondack_park_boundary`: Adirondack Park Boundary (the Blue Line), 1 polygon feature; places
  kind `park`.
- `dec_catskill_park_boundary`: Catskill Park Boundary (the Blue Line), 1 polygon feature; places kind
  `park`.

The Adirondack and Catskill boundaries carry no name column, so their rows declare `name_constant`.
"""

from extract._kinds import arcgis_layer

CLAIMS = (
    "dec_lands",
    "dec_conservation_easements",
    "dec_wildlife_management_areas",
    "dec_adirondack_park_boundary",
    "dec_catskill_park_boundary",
)
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
