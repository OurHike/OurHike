"""Superior Hiking Trail Association: photos, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav and footer checked (Facebook, Instagram and YouTube only).",),
    where=(
        "https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services",
        "https://superiorhiking.org/",
    ),
)
