"""The Maah Daah Hey Trail Association's elevation: the Z on every vertex of the trail guide's GeoJSON
lines, which mdhta/trail_lines.py extracts as `mdhta_trail_guide` (decision 54, wave 2, read
2026-10-04).

One vertex read against 3DEP gives the unit as metres (`[-103.4449419, 46.5982664, 774.478]` against
EPQS's 775.02 m, 2026-10-03), which is one point, not a measurement of the files: the row's
`elevation_unit_comment` is @unvalidated, and nothing calibrates from this Z until a sample along each
line against 3DEP settles it and whether it came from GPS or a DEM. The trail pages' `elevation-profile-
holder` is drawn from the same files. This file was the note that said it would become SHARES once
trail_lines.py loaded them.
"""

SHARES = "trail_lines"
