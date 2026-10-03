"""NC Mountains-to-Sea Trail (state-published layer): places, drawn from nc_dpr/'s resources (decision 54,
wave 1, read 2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via nc_dpr `nc_state_park_boundaries` (NC_State_Parks_System/FeatureServer/0, 346 polygons, last edited "
        "2026-10-02), registered 2026-10-03. `State_Owned_Land_(Latest)` was not read.",
    ),
    where=(
        "https://services6.arcgis.com/nRIB86xC7kq6wavB/arcgis/rest/services/NC_State_Parks_System/FeatureServer/0",
        "https://trails.nc.gov/",
    ),
    reason=(
        "drawn from nc_dpr/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
