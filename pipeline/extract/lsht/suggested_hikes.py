"""Lone Star Hiking Trail Club: suggested hikes, refused by the host (decision 54 wave 4, section K,
2026-10-04).

lonestartrail.org answered HTTP 403 Forbidden (an AWS load balancer's page, 118 bytes) to our named agent on
2026-10-04, its robots.txt and the Grand Loop Hike document (docs.ashx?id=1469733) alike; nothing past it was read
or retried. Decision 53's inventory had already found the ClubExpress Terms of Use answering only with a session
(lsht's closures file). The thru-hikers' guide and the 11 section maps stay the coverage audit's description.

The note this replaces read, whole:

Lone Star Hiking Trail Club: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Turn-by-turn thru-hikers' guide (page and PDF); "The Grand Loop
Hike" (`docs.ashx?id=1469733`); 11 section maps with mileages.

Its `where`: https://apps.fs.usda.gov/arcx/rest/services https://lonestartrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://lonestartrail.org/: HTTP 403 (118 bytes, Server awselb/2.0) to our agent, 2026-10-04T17:46:01Z; robots.txt also 403",
        "https://lonestartrail.org/docs.ashx?id=1469733: HTTP 403, 2026-10-04",
    ),
    where=("https://lonestartrail.org/",),
    reason="refused: the host answers HTTP 403 to our named agent",
)
