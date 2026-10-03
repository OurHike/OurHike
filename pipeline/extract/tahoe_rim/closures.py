"""Tahoe Rim Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Format page: `tahoerimtrail.org/current-trail-conditions/`, per segment, "Updated August 17, 2026". '
        'Example: "The dispersed camping area at Watson Lake is scheduled to close November…". '
        "`Camping_Prohibited/0` (12 polygons, 2016) and `Camping_Restrictions/0` (1, 2020) are standing rules.",
    ),
    where=("https://tahoerimtrail.org/current-trail-conditions/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
