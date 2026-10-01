"""Mazamas: warnings, nothing published (coverage audit 2026-10-01, batch p04_persist).

avalanche.org is explicit_restriction: "Please contact avalanche.org / American Avalanche Associate
for permission" (API root page). If loaded, it would go in `_shared/` (a new source), not here.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Tried: as for closures. `/avalanche/` is a seminar calendar ("Avalanche Awareness Seminars … Upcoming '
        'seminars, workshops, and courses"), not a hazard notice. The avalanche.org public map layer has an '
        'NWAC "Mt Hood" zone, which is off-season today (`danger: no rating`).',
    ),
    where=(
        "https://avalanche.org",
        "https://mazamas.org/",
    ),
)
