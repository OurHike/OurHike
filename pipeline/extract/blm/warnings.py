"""Bureau of Land Management: warnings, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Shooting points are areas set aside for target shooting. Whether that counts as a hiker hazard
warning is a maintainer call. Skeptic: fire restrictions are page format, one page per state.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same press-release RSS (e.g. Utah "BLM to Reduce Hazardous Fuels around Grover, Utah"). A "Fire '
        "Restrictions\" page is linked from blm.gov's navigation. "
        "`https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/BLM_Qualified_Shooting/FeatureServer/0`"
        ' ("BLM Natl EXPLORE Recreational Shooting Points", owner `an email address`, item modified '
        "2026-04-21): 93 points.",
        "Skeptic (Measured 2026-10-01): `https://www.blm.gov/programs/fire/fire-restrictions` opened. It is a "
        "page of 14 state links, Alaska through Wyoming; Nevada's goes to "
        "`https://www.nevadafireinfo.org/restrictions`, off …",
    ),
    where=(
        "https://services1.arcgis.com/KbxwQRRfWyEYLgp4/arcgis/rest/services/BLM_Qualified_Shooting/FeatureServer/0",
        "https://www.blm.gov/programs/fire/fire-restrictions",
        "https://www.nevadafireinfo.org/restrictions",
        "https://blm.gov",
        "https://gis.blm.gov/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
