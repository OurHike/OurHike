"""Old Dominion Appalachian Trail Club: suggested hikes, two circuit hikes on one page, and not landed
(decision 54 wave 4, section K, 2026-10-04).

odatc.org/page-1503143 (a Wild Apricot page) describes two circuit hikes in prose: Humpback Rocks, whose
description and map are hikingupward.com's, and the Albright Loop, with ODATC's own PDF map. Two hikes in
paragraphs are a page a person reads; odatc.org's robots.txt asks `Crawl-delay: 10`.

The note this replaces read, whole:

Old Dominion Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Only the Albright Trail is the club's own.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/page-1503143` (page): 2 circuit hikes. For Humpback Rocks, the
description and map are third-party (`hikingupward.com`); for the Albright Trail, ODATC's own PDF map

Its `where`: https://hikingupward.com

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.odatc.org/page-1503143 (HTTP 200, 30,143 bytes, 2026-10-04T17:39:16Z): no headings; two PDFs, /resources/Documents/Albright%20Loop%20Map.pdf and hikingupward.com's map",
    ),
    where=("https://www.odatc.org/page-1503143",),
    reason="needs a per-site reader, not built in this pull request: two hikes whose facts are inside paragraphs",
)
