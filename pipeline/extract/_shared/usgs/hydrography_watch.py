"""The usgs_3dhp watch: whether USGS's 3D Hydrography Program has resurveyed the A.T. corridor yet.

3DHP is the successor to the retired NHD this pipeline's water derivation
depends on, and for the corridor it republishes NHD unchanged, so migrating
today would cost the perennial/intermittent classification and buy nothing
(WATER_SOURCES.md §5). This lands the answer, five probe boxes' work units,
and no geometry. It feeds no mart: its verdict is an invitation to cost a
migration, read by a person (check_freshness.py). Monthly, as the rest of
the reference data is.
"""

from extract._kinds import hydrography_watch

TYPE = "points_of_interest"
CLAIMS = ("usgs_3dhp",)
RESOURCES = [hydrography_watch("usgs_3dhp")]
