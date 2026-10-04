"""The U.S. Census Bureau's TIGER/Line state boundaries, as `raw_census__census_tiger_states`, on the monthly lane.

Decision 76 (pipeline/ELT.md, 2026-10-04): a state-wide agency notice, such as
BLM's Utah fire restrictions, shows to a hike planned in that state that walks
that agency's trails. The phone has to tell whether a route is in a state, and
nothing it held could, so it gets the states' shapes. A federal statistical
agency is no club, so the file sits in _shared/ (decision 18).

`places` is the type because a state is a named area read monthly, and the
type sets the lane; no places model reads this table. Its one reader is
int_closures__notice_state_shapes, which simplifies only the states
dbt/seeds/notice_states.csv names, for conditions/notice_states.json. The app
never draws them.

One row per state or equivalent (56 on 2026-10-04), keyed by `stusps`, the
whole file read when its Last-Modified or length moves. Its row in
sources.json holds the counts, the validators and the terms.
"""

from extract._gis_files import gis_file

TYPE = "places"
CLAIMS = ("census_tiger_states",)
RESOURCES = [gis_file(key) for key in CLAIMS]
