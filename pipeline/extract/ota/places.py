"""Ozark Trail Association: places, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/trail-services/`: shuttles, resupply and lodging, each tagged with the sections it serves. "
        "`/list-of-contacts/`: land managers. The section pages list land managers and emergency numbers.",
    ),
    where=("https://ozarktrail.com/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
