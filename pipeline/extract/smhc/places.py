"""Smoky Mountains Hiking Club: places, drawn from nps/'s resources (decision 54, wave 1, read 2026-10-03)."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via nps `nps_park_boundaries` (UNIT_CODE 'GRSM'), `grsm_municipal_boundaries` (GRSM_MUNICIPAL_BOUNDARIES/0, 22 "
        "gateway towns: Gatlinburg, Cherokee, Bryson City, Townsend and the rest A.T. Communities lacks) and "
        "`grsm_park_boundary_lines` (GRSM_PARK_BOUNDARY/0, 19 lines), registered 2026-10-03. GRSM_TRAILHEADS/0 (154) and "
        "GRSM_PARKING/0 (673) are points_of_interest's. Fontana Dam arrives through atc `communities`.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_MUNICIPAL_BOUNDARIES/FeatureServer/0",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/GRSM_PARK_BOUNDARY/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in",
)
