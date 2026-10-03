"""Hoosier Hikers Council: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "18 trail pages under the Trails menu (pages). The Tecumseh Trail Guide PDF. "
        '`/assets/Bicentennial_Trail_List.pdf` (2,078,142 bytes, "Updated: Feb. 2, 2020"), a table of trail, '
        "property, county and miles.",
    ),
    where=("https://hoosierhikerscouncil.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
