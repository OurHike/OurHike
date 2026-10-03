"""The Anza Trail Foundation: places, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: County Guides `https://anzahistorictrail.org/county/` (WordPress). `NPSAPI/places` juba ≥10; visitor centers 8",
    ),
    where=(
        "https://anzahistorictrail.org/county/",
        "https://anzatrailfoundation.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
