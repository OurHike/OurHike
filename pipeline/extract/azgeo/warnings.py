"""AZGeo Data Hub: warnings, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

The Arizona Trail Association's closures category (https://aztrail.org/category/closures-reroutes/),
which the coverage audit filed here, is ATA's and is read once in ata/closures.py as
`ata_closures_reroutes` (decision 34); its feed and listing page are that category's window and its
human view, and are not read.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/USFS_Camping_and_Campfire_Restricted_Area/FeatureServer/0,
a 2023 copy of a Coconino NF order (lastEditDate 2023-05-09); the Forest Service's own R3 order
layers in usfs/ are the live channel.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        'The same feed\'s category is "Current Closures, Restrictions, and Reroutes" (org_channels). Items not read.',
        "via ata/ `ata_closures_reroutes` (decision 53 phase B, 2026-10-03): WordpressPosts, category 251, X-WP-Total 13",
    ),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services",
        "https://azgeo-open-data-agic.hub.arcgis.com/",
        "https://aztrail.org/category/closures-reroutes/",
    ),
    reason="drawn from ata/'s `ata_closures_reroutes`, extracted once there (decision 34): ATA's closures category carries its warnings too (concertina wire, camping restrictions)",
)
