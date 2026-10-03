"""Appalachian Mountain Club (A.T. sections): closures, published, and not landed (coverage audit
2026-10-01, batch c1_at_clubs_north).

A hut's open or closed status is a facility closure. The NH A.T. rows ATC carries (2, including the
Great Gulf bridge closure that obstructs the trail) are LOADED via `atc_trail_updates`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.outdoors.org/weather-trail-conditions/` (page): per-destination "Current Conditions" and '
        '"Status: Open" for every hut and lodge.',
    ),
    where=("https://www.outdoors.org/weather-trail-conditions/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
