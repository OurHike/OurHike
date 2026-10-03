"""Iditarod Historic Trail Alliance: challenges, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

A ready-made #1780 candidate once the 9 locations are geocoded

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`passport-stamp-program.html`: "a total of 9 stamps at different locations along the trail" (page; '
        "list in Visitor Guide p.14). BLM page "
        "`blm.gov/documents/alaska/public-room/educational-material/iditarod-national-historic-trail-passport-program`."
        ' "Junior Trailblazer" page',
    ),
    where=(
        "https://blm.gov/documents/alaska/public-room/educational-material/iditarod-national-historic-trail-passport-program",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
