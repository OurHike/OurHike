"""Texas Trail Tamers: warnings, published, and not landed (coverage audit 2026-10-01, batch
p05_persist).

As closures. Folder `tpwd/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'McKinney Falls: "Burn Ban Aug. 11, 2026 - The park is under a burn ban. Wood fires are not allowed." '
        'Davis Mountains: "Burn Ban Jan. 1, 2026 - No wood fires are allowed." Tried: as closures.',
    ),
    where=(
        "https://services1.arcgis.com/1mtXwieMId59thmg/arcgis/rest/services",
        "https://tpwd.texas.gov/arcgis/rest/services",
        "https://texastrailtamers.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
