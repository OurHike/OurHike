"""Maah Daah Hey Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch q01_persist).

Format: page. The fire closure order is the one a hiker most needs, and it is only a page. Licence:
USFS public domain (federal) → open_licence (public domain, federal). Folder: `usfs/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.fs.usda.gov/r01/dpg/alerts` (the FAQ's `fs.usda.gov/alerts/dpg/alerts-notices` redirects "
        "there), page, 9 alert links, including "
        "`little-missouri-national-grassland-fire-closure-order-01-18-00-26-02`, "
        "`area-closure-vehicles-road-little-missouri-national-grassland`, "
        "`road-closure-national-forest-system-roads-747-and-7471-medora-ranger-district`, "
        "`road-closure-nfsr-735a-9`. GIS is empty here: `EDW_RecreationOpportunities_01` within 1 km of the "
        "144.98-mi `usfs_trails` MDH line (31 features): 5 sites, all `openstatus` 'none'. Dakota Prairie "
        "forest-wide: none 21, open 1, so the field …",
    ),
    where=(
        "https://www.fs.usda.gov/r01/dpg/alerts",
        "https://fs.usda.gov/alerts/dpg/alerts-notices",
        "https://ndgishub.nd.gov/arcgis/rest/services",
        "https://mdhta.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
