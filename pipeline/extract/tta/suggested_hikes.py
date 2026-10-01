"""Tennessee Trails Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

The events are dated outings, not routes. Terms forbid republishing.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/hikes-events/36-fran-wallas-hikes/` lists 36 named hikes (HTML). PDF of Great Hikes in Tennessee "
        "State Parks: `/wp-content/uploads/2021/03/Great_Hikes_Fran-Wallas-2021.pdf`. Events REST "
        "`/wp-json/tribe/events/v1/events` (72 upcoming group hikes). "
        "`/2025-agm-hike-schedule-and-descriptions/` (page).",
    ),
    where=("https://tennesseetrails.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
