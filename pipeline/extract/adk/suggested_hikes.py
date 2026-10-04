"""Adirondack Mountain Club: suggested hikes, refused by ADK's own terms (decision 54 wave 5, section K,
2026-10-04).

ADK publishes hikes as posts and pages: 'Shoulder Season Hikes' holds a table of 29 rows ('Hike | Area | Why It
Works for Shoulder Season'). ADK's Terms & Conditions refuse what a reader does, in the words decision 53 already
read as a refusal for ADK's conditions report (adk/closures.py): 'you will not access the Services through
automated or non-human means, whether through a bot, script or otherwise', and among the prohibited activities
'Systematically retrieve data or other content from the Services to create or compile, directly or indirectly, a
collection, compilation, database, or directory without written permission from us'. Nothing past the page and
the terms was read; the route forward is ADK's written permission.

The note this replaces read, whole:

Adirondack Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

The skeptic made no requests to adk.org, because ADK's terms bar automated access. These URLs come from
a search engine's index and were not opened. Blog-style pages. The same written-permission gate applies.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): A web search restricted to adk.org (2026-10-01) returns
`https://adk.org/hiking-mount-jo-the-perfect-first-adirondack-summit/` ("just over two miles round trip
with approximately 700 feet of elevation gain… two routes to the summit"),
`https://adk.org/shoulder-season-hikes/` (Mount Jo, Goodman, Coney, Baxter, Mount Arab), and
`https://adk.org/explore/first-time-visitor/` ("beginner-friendly hikes"). The guidebook "Peaks and
Ponds" (37 day hikes) is sold.

Its `where`: https://adk.org/hiking-mount-jo-the-perfect-first-adirondack-summit/
https://adk.org/shoulder-season-hikes/ https://adk.org/explore/first-time-visitor/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://adk.org/shoulder-season-hikes/ (HTTP 200, 2026-10-04): a table of 29 rows, 'Hike | Area | Why It Works for Shoulder Season', 4 of them repeated",
        "https://adk.org/terms-conditions/ (HTTP 200, 2026-10-04), its section 3 and its prohibited activities, quoted in `terms`",
    ),
    where=(
        "https://adk.org/shoulder-season-hikes/",
        "https://adk.org/terms-conditions/",
    ),
    terms="'you will not access the Services through automated or non-human means, whether through a bot, script or otherwise' ... 'Systematically retrieve data or other content from the Services to create or compile, directly or indirectly, a collection, compilation, database, or directory without written permission from us.' ... 'Engage in any automated use of the system, such as using scripts to send comments or messages, or using any data mining, robots, or similar data gathering and extraction tools.'",
    reason="refused: ADK's terms forbid access by automated means and systematic retrieval without written permission",
)
