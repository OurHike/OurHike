"""Laurel Highlands Hiking Trail (PA DCNR): places, drawn from pasda/'s resources (decision 54, wave 1,
read 2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via pasda `dcnr_state_park_boundaries` (DCNR's Parks/State_Parks/MapServer/9, 125 polygons, Laurel Ridge, Laurel"
        " Hill and Laurel Summit state parks among them) and `dcnr_state_forest_boundaries` "
        "(BOF/State_Forests/MapServer/4, 662), registered 2026-10-03.",
    ),
    where=(
        "https://www.gis.dcnr.pa.gov/agsprod/rest/services/Parks/State_Parks/MapServer/9",
        "https://www.gis.dcnr.pa.gov/agsprod/rest/services/BOF/State_Forests/MapServer/4",
    ),
    reason=(
        "drawn from pasda/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in"
    ),
)
