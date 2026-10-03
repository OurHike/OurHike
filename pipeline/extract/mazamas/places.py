"""Mazamas: places, nothing published (coverage audit 2026-10-01, batch p04_persist).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/mazamalodge/` and `/mmc/` are the club's own buildings (audit). Tried: items (1)–(6) as for "
        'trail_lines. The Multnomah "Mazamas 125 Years" places layer was the one candidate, and its service is '
        "gone (HTTP 500).",
    ),
    where=("https://mazamas.org/",),
)
