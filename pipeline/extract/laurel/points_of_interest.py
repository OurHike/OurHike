"""Laurel Highlands Hiking Trail (PA DCNR): points of interest, drawn from pasda/'s resources.

The LHHT's shelter areas are rows of PA DCNR's state park buildings layer (USE1 'Trail Shelter'; the coverage
audit matched 40 to DCNR's own description), extracted once as pasda_state_park_buildings in
pasda/points_of_interest.py (decision 34). Its access points are Explore PA Trails', pasda_explore_pa_trail_access.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "StateParkBuildingsMASTER/MapServer/0, 4,359 points with USE1 'Trail Shelter' on 55 (read "
        "2026-10-03), registered as pasda_state_park_buildings and extracted in pasda/",
        "ExplorePAtrails/MapServer/2, 3,030 access points (read 2026-10-03), registered as "
        "pasda_explore_pa_trail_access and extracted in pasda/; the coverage audit counted 6 for the LHHT",
    ),
    where=(
        "https://www.gis.dcnr.pa.gov/agsprod/rest/services/Parks/StateParkBuildingsMASTER/MapServer/0",
        "https://mapservices.pasda.psu.edu/server/rest/services/pasda/ExplorePAtrails/MapServer/2",
    ),
    reason=(
        "drawn from pasda/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in"
    ),
)
