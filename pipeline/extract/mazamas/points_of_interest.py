"""Mazamas: points of interest, nothing published (coverage audit 2026-10-01, batch p04_persist).

Mazama Lodge is the club's own building, not a trail POI. Its land manager is Mt. Hood NF, whose rec
sites are in `usfs` (loaded as `EDW_RecInfraRecreationSites_02`).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nothing found. Tried: items (1), (2), (5) and (6) as for trail_lines; `/stewardship/` and "
        "`/stewardshipopportunities/` are activity calendars and prose with no locations; no Google My Maps "
        "`mid=` anywhere on `/climbroutes/` or `/streetrambles/routes-maps/` (the only embeds are the two Drive"
        " folders).",
    ),
    where=("https://mazamas.org/",),
)
