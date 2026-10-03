"""Lewis & Clark Trail Heritage Foundation: places, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Format: WordPress REST plus an app

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: `https://lewisandclark.travel/` ("Lewis and Clark Trail Experience", WordPress; `/wp-json/` '
        "answers 200, 311 KB index; also VisitWidget apps). `NPSAPI/places` lecl ≥137",
    ),
    where=(
        "https://lewisandclark.travel/",
        "https://lewisandclark.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
