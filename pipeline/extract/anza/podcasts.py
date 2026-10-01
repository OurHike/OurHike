"""The Anza Trail Foundation: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: `anzahistorictrail.org/junior-rangers/listen/` "Sounds of Nature & Culture". '
        '`NPSAPI/multimedia/audio` juba 12 ("Modern Stories" voices)',
    ),
    where=("https://anzahistorictrail.org/junior-rangers/listen/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
