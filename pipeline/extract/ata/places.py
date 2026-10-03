"""Arizona Trail Association: places, drawn from azgeo/'s resources (decision 54, wave 1, read 2026-10-03)."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "via azgeo `azt_gateway_communities` (Gateway_Community_Points/FeatureServer/0, 22 points owned by ATA's own "
        "account), `azt_passage_areas` (layer 6 of the AZT feature-layer view, 138 polygons) and `azt_land_ownership` (32"
        " polygons), all registered 2026-10-03 from the ArcGIS Online organization azgeo_arizona_trail is read from. "
        "ATA's page `/explore/gateway-communities/` lists 20 towns.",
    ),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
        "https://aztrail.org/",
    ),
    reason=(
        "drawn from azgeo/'s resources, extracted once there (decision 34); checked names the layers this org's data arrives in"
    ),
)
