"""Mountains to Sound Greenway Trust: warnings, published, and not landed (coverage audit 2026-10-01,
batch p04_persist).

Licence class (DNR): attribution_only, copyrightText "Department of Natural Resources (DNR),
Wildfire Division", with no licenseInfo. The fields `REGION_PHONE_NO` and `REGION_EMAIL_ADDR` are
regional-office contacts, not individuals. avalanche.org is explicit_restriction. The data belongs
in …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WA DNR "
        "`https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer/0`"
        ' ("Wildfire Danger", polygons): 23 statewide (Moderate 20, Low 3). 7 intersect the NHA: North Cascade,'
        " North Lowlands and Central WA Cascades are Low; Lower Basin, Upper Yakima, Chelan and Central "
        'Lowlands are Moderate. `BURN_BAN_LEVEL_NM` carries the burn ban. Layer 1 is "Burn Bans". King County '
        '`AlertType=\'Hazard\'` has 5 active rows (audit). avalanche.org NWAC zones "Snoqualmie Pass", "West '
        'Slopes Central" and "East Slopes Central", off-season today. WA Parks …',
    ),
    where=(
        "https://gis.dnr.wa.gov/site3/rest/services/Public_Wildfire/WADNR_PUBLIC_WD_WildfireDanger/MapServer/0",
        "https://avalanche.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
