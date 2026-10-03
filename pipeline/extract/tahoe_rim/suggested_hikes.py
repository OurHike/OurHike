"""Tahoe Rim Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Format page: `tahoerimtrail.org/day-hiking/` ("Day Hike Itineraries": Alpine Lakes, Wildflower, Peaks '
        '& Vistas, Waterfall) and "How to break the Tahoe Rim Trail into 14 Day Hikes".',
    ),
    where=("https://tahoerimtrail.org/day-hiking/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
