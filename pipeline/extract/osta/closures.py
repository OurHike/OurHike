"""Old Spanish Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

Own: UNKNOWN

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAPI/alerts?parkCode=olsp`: 0 today. Page `home.nps.gov/olsp/planyourvisit/conditions.htm` (search index)",),
    where=("https://home.nps.gov/olsp/planyourvisit/conditions.htm",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
