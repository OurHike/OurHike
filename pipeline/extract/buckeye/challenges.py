"""Buckeye Trail Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Restricted. The programme only, not the list of names.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/hike/awards`: "Personalized Completionist Patch", "Little Loop Patch", and a list of Completionists.'
        ' Circuit hikes run as events (e.g. "Little Loop Circuit Hike #14", 2026-10-03).',
    ),
    where=("https://buckeyetrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
