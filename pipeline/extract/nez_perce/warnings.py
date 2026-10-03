"""Nez Perce (Nee-Me-Poo) Trail Foundation: warnings, drawn from usfs/closures.py's alerts page for the
trail (decision 53 phase B, 2026-10-03).

The page's Fire Restriction and Caution levels are the warnings half of `usfs_nez_perce_nht_alerts`,
which lands once in usfs/closures.py (decision 34) and which the warnings staging model reads too.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c11_nht), whose `checked` read "Same page: Fire Restriction and Caution categories".
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "usfs/closures.py `usfs_nez_perce_nht_alerts` reads https://www.fs.usda.gov/trails/nez-perce-nht/alerts "
        "(decision 53 phase B, 2026-10-03): its Fire Restriction and Caution levels are this type's; 0 alerts "
        "that day.",
        "(coverage audit, 2026-10-01) its note listed the ArcGIS root on apps.fs.usda.gov and two ArcGIS Online "
        "orgs among where it looked, and registered no layer from them.",
    ),
    where=(
        "https://www.fs.usda.gov/trails/nez-perce-nht/alerts",
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://services1.arcgis.com/CPCzfCPkoQSKO5TC/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://nezpercetrail.net/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the page this org's notices arrive in",
)
