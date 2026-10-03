"""NJDEP / NJGIN — Statewide Trails: places, extracted (decision 54, wave 1; live read 2026-10-03 under
lib/user_agent.py's USER_AGENT).

- `nj_state_open_space`: State Protected Open Space (Generalized) and Recreation Areas in New Jersey,
  373 polygon features; places kind `park`.
- `nj_state_natural_areas`: State Natural Areas in New Jersey, 47 polygon features; places kind `park`.
- `nj_parks_points`: Parks (points), NJDEP Features/Land, 394 point features; no places kind.
- `nj_place_names`: Place Names (GNIS-derived points), NJDEP Features/Land, 2,641 point features; places
  kind `town`.

Not read this time: Open_Space/66 (95,032 parcels of every owner) and Land/81 Hidden Gems (71). The
state open-space points of interest are the points_of_interest file's.
"""

from extract._kinds import arcgis_layer

CLAIMS = ("nj_state_open_space", "nj_state_natural_areas", "nj_parks_points", "nj_place_names")
RESOURCES = [arcgis_layer(key) for key in CLAIMS]
