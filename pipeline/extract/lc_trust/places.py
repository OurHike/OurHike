"""Lewis and Clark Trust: places, published, and not landed (coverage audit 2026-10-01, batch c11_nht).

Ten items

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/wp-json/wp/v2/allied_site`: `X-WP-Total` 10 (e.g. Big Bone Lick State Historic Site), WordPress "
        "REST, no coordinates in the REST body",
    ),
    where=("https://lewisandclark.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
