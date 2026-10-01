"""Standing Stone Trail Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Page. The hunting dates are explicit.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/trail-alerts`: "NOTICE: WEAR BLAZE ORANGE November 15 to December 15 ALL TRAIL SECTIONS"; "Many '
        "sections of trail are 'Active In-Season Hunting Zones'\"; it also links DCNR's \"2023 Rothrock State "
        'Forest Management Activities" PDF (stale).',
    ),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://standingstonetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
