"""Nez Perce (Nee-Me-Poo) Trail Foundation: places, drawn from nps/'s resources (decision 54, wave 1, read
2026-10-03).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via nps `nps_park_boundaries` (442 polygons, UNIT_CODE 'NEPE' one of them), registered 2026-10-03. The USFS "
        "Region 1 centerline is trail_lines', and the NPS API's places need a key (wave 3).",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/FeatureServer/2",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
