"""The Palmetto Trail's 33 passage lines, which palmetto/points_of_interest.py extracts as
`palmetto_trail_passages` with each passage's map markers: one page per passage, one upstream, one resource
and one raw table (decision 34).

Each passage page draws its line from `trailPage.helper.addSegment(<name>, [{"lng", "lat"}, ...], [])` in its
own script (read live 2026-10-04: 33 lines, 70,104 vertices). The row's `kind` 'segment' marks them, and
int_trail_lines__club_lines keeps only the lines. Partly drawn already by usfs_trails (about 92.3 mi, the
coverage audit's correction 7), so the dedupe after the load meets them there. A club line draws and never
routes until that dedupe has checked it (decision 64). Not read: the 313,124,546-byte Mobile Map Package
'Palmetto Trail - Statewide Map' on the foundation's ArcGIS account, a binary package rather than a service,
and the per-passage Avenza maps.
"""

SHARES = "points_of_interest"
