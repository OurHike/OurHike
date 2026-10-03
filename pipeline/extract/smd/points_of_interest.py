"""Save Mount Diablo: points of interest, published, and not landed (coverage audit 2026-10-01, batch
p06_persist).

Nothing found covers SMD's own preserves (Curry Canyon Ranch, Mangini Ranch).; EBRPD licence:
attribution_only. licenseInfo: "Disclaimer EBRPD makes every effort to provide useful and accurate
information… represents only the approximate relative locations… By using this site/maps you agree
to the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "EBRPD (counts in the box -122.10,37.78 to -121.75,38.02, with the statewide or district total in brackets):",
        "`services2.arcgis.com/jeEP9c9zZoQQwtck/arcgis/rest/services/Drinking_Fountains/FeatureServer/6`: 43 (402)",
        "`Restrooms/FeatureServer/5`: 24 (272)",
        "`Park_Entrances_PF/FeatureServer/4`: 52 (412); Data last edited 2026-04-09 (fountains and restrooms) "
        "and 2024-10-10 (entrances).; CDPR:",
        "`services2.arcgis.com/AhxrK3F6WM8ECvDi/arcgis/rest/services/Campgrounds/FeatureServer/0`: 9 in the box"
        " (531 statewide), data edited 2026-09-02",
        "`Park_Pass_Park_Entry_Points`: one entrance point per …",
    ),
    where=(
        "https://services2.arcgis.com/jeEP9c9zZoQQwtck/arcgis/rest/services/Park_Entrances_PF/FeatureServer/4",
        "https://services2.arcgis.com/jeEP9c9zZoQQwtck/arcgis/rest/services/Drinking_Fountains/FeatureServer/6",
        "https://services2.arcgis.com/AhxrK3F6WM8ECvDi/arcgis/rest/services/Campgrounds/FeatureServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
