"""Lewis & Clark Trail Heritage Foundation: photos, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Own photos are not open

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAPI/multimedia/galleries` lecl 8. Own `/photo-contest/` shows winners with no licence stated (sold as a calendar)",
    ),
    where=("https://lewisandclark.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
