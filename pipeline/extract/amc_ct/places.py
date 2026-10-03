"""AMC Connecticut Chapter: places, drawn from ct_deep/'s resources (decision 54, wave 1, read 2026-10-03)."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via ct_deep `ct_deep_property` (Connecticut_DEEP_Property/FeatureServer/0, 491 polygons, CC0), registered "
        "2026-10-03: Housatonic State Forest, Kent Falls SP, Macedonia Brook SP and the other units along Connecticut's "
        "A.T. The access-point layer DEEP_Property_Access_Locations/0 (385) is points_of_interest's.",
    ),
    where=(
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/Connecticut_DEEP_Property/FeatureServer/0",
        "https://ct-amc.org/",
    ),
    reason=(
        "drawn from ct_deep/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
