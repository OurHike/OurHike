"""Potomac Heritage Trail Association: places, drawn from nps/'s resources (decision 54, wave 1, read
2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via nps `pohe_trail_regions` (POHE_Trail_Regions_View/FeatureServer/4, 9 management regions) and "
        "`nps_park_boundaries`, registered 2026-10-03. The NPS API's /places for pohe needs a key (wave 3).",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/POHE_Trail_Regions_View/FeatureServer/4",
        "https://nps.gov/pohe/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); the NPS API's places are not landed yet",
)
