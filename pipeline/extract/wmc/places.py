"""Wasatch Mountain Club: places, drawn from utah_sgid/'s resources (decision 54, wave 1, read 2026-10-03)."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via utah_sgid `ugrc_local_parks` (UtahParksLocal/0, 2,104 statewide), `ugrc_municipal_boundaries` (261) and "
        "`ugrc_state_park_boundaries` (47), registered 2026-10-03. UtahWildernessAreas compiles the wildernesses usfs/ "
        "registers (`usfs_wilderness_areas`), so it is not registered.",
    ),
    where=(
        "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services",
        "https://wasatchmountainclub.org/",
    ),
    reason="drawn from utah_sgid/'s and usfs/'s resources, extracted once there (decision 34); checked names the layers",
)
