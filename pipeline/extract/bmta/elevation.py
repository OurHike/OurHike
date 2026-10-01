"""Benton MacKaye Trail Association: elevation, nothing published (coverage audit 2026-10-01, batch
c8_regional_5).

USGS 3DEP covers it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/discover-the-trail/` shows totals ("Ascent: 54,682′ … High: 5,779′ Low: 755′"). They appear to come '
        "from the Hiking Project embed, not from a BMTA product.",
        'Skeptic: the store sells a "Pocket Profile Map of Benton MacKaye Trail", $12.95 '
        "(`/product/pocket-profile-map-of-benton-mackaye-trail/`). Its own description says \"'Tinman' from "
        "Anti-Gravity Gear has published\" it, so it is a third party's print product resold by the BMTA. That "
        "supports NOT_PUBLISHED.",
    ),
    where=("https://bmta.org/",),
)
