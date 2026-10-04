"""The Mountaineers: suggested hikes, behind a wall that refuses our agent (decision 54 wave 5, section K,
2026-10-04).

The Routes & Places library (mountaineers.org/activities/routes-places) answered HTTP 403 to lib/user_agent.py's
agent on 2026-10-04, with robots.txt read first and allowing the path. A host that refuses our own named agent has
refused us (decision 39): nothing past it was asked, and no other agent was tried.

The note this replaces read, whole:

The Mountaineers: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Routes & Places route records in the search index (e.g.
`/activities/routes-places/granite-mountain-trail`, `argonaut-peak-south-route`). Their snippets list
land manager, parking, party size and recommended maps, the same Plone product as CMC's.

Its `where`: https://mountaineers.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.mountaineers.org/activities/routes-places: HTTP 403 (5,610 bytes) to our agent, 2026-10-04; robots.txt allows the path",
    ),
    where=("https://www.mountaineers.org/activities/routes-places",),
    reason="refused: the host answers HTTP 403 to our named agent",
)
