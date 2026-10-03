"""The Mountaineers: closures, could not be told (coverage audit 2026-10-01, batch p09_persist).

Even when readable, the blog posts are relays of the agencies' own closures. Folders: `usfs/`,
`nps/`, WA DNR, WA State Parks.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The search index shows the club writes closure prose that relays land managers: "
        "`/blog/navigating-closures-staff-reductions-and-timed-entry-at-mount-rainier-this-summer` and "
        "`/blog/public-land-closures-reopenings-during-covid-19`. Both are behind the wall. Tried: (2) AGOL "
        'found "WA DNR Closures" (`6598a696556d4ef19e124818bbcb97c3`), owner a personal ArcGIS account, a '
        "personal UW account (a lead, not DNR's), and WA State Parks `WinterRecAreaClosure` (2023-10-20). (4) "
        "Land managers: USFS closure lines and `openstatus` (audit b6); NPS alerts for MORA, NOCA and OLYM not "
        "measured (API rate limit). …",
    ),
    where=("https://mountaineers.org/",),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
