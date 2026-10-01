"""Society for the Protection of NH Forests: challenges, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/challenge`: the Forest Reservation Challenge, 33 featured reservations (33 "
        "`forest-reservation-challenge-` pages), Tier 1/2, patch and decal. `/Fivehikeschallenge2026`: 15 "
        'Aug–31 Oct, with 25 hidden "tree cookies".',
    ),
    where=(
        "https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services",
        "https://forestsociety.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
