"""The Anza Trail Foundation: closures, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`NPSAPI/alerts?parkCode=juba`: 0. `anzahistorictrail.org/explore/`: "Please contact the land manager '
        'for the most up-to-date trail conditions"',
    ),
    where=("https://anzahistorictrail.org/explore/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
