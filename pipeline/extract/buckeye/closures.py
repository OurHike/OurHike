"""Buckeye Trail Association: closures, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Restricted. Kirby CMS pages, with no feed found. Alerts are keyed to Section "Points", so locating
them needs BTA's point data.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Each section page\'s "Trail Alerts" block: 38 entries across 26 sections, 5 of them "No Active Alerts" '
        'placeholders. Current examples: "Loveland Trail Closure PT 10 -11" (2026-09-24), "Stockport Section '
        'Trail Alert Pt 4" (2026-09-18), "Whipple Trail Alert - Closure Pts 1 to 4" (2026-09-15), "New '
        'Straitsville Alert Pt 4 to Pt 13 Flooding Closure" (2026-08-18), "Scioto Trail - Closure Pt 25 - Pt '
        '26" (2026-08-17). Each links to `/updates/<uuid>`. There are also 237 "Map Updates", which are '
        "permanent reroutes.",
    ),
    where=("https://buckeyetrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
