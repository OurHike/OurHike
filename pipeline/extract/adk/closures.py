"""Adirondack Mountain Club: closures, refused by ADK's own terms (decision 53 phase B, 2026-10-03).

ADK publishes its High Peaks Conditions Report as one WordPress page
(https://adk.org/explore/high-peaks-conditions-report/, page 1544). robots.txt does not refuse it:
adk.org's robots.txt carries Cloudflare content-signal comments and no rule. ADK's terms do, in
words decision 55 counts among the refusals: they forbid access 'through automated or non-human
means' (quoted in `terms`). So nothing is fetched past the inventory's one read of the page and the
terms, and the route forward is ADK's written permission, recorded as decision 47 records ATC's. It
lists closures as prose bullets (lean-tos closed, a lean-to burned, Station Street parking closed,
three Marcy Dam campsites closed) with no id per item and no geometry. DEC is the land manager;
DEC's channels are nysdec/'s. NPT, ADK's chapter, no longer has a conditions page:
https://nptrail.org/current-trail-conditions/ now serves WordPress page 144, 'Trail Maps'.

Before decision 53 phase B, 2026-10-03, this note read:

Adirondack Mountain Club: closures, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page, updated frequently. Terms bar automated access. DEC is the land manager.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://adk.org/explore/high-peaks-conditions-report/`, dated
"Wednesday, September 30". It lists closures: Lapland and Black Mountain Pond lean-tos closed,
Fishbrook Pond North lean-to burned down, the Calamity Brook high-water bridge washed out, Avalanche
Pass reopened. Also `https://nptrail.org/current-trail-conditions/` (Sucuri JS wall, not fetched).

Its `where`: https://adk.org/explore/high-peaks-conditions-report/
https://nptrail.org/current-trail-conditions/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(the decision 53 inventory, batch 1, 2026-10-03) https://adk.org/explore/high-peaks-conditions-report/: 200, one WordPress page (id 1544, JSON-LD dateModified 2026-10-02T12:59:36Z); robots.txt holds no rule for the path. The terms page, read whole, forbids automated access (quoted in `terms`).",
        "(the inventory, batch 1) https://nptrail.org/current-trail-conditions/: 200, now WordPress page 144 'Trail Maps' with no conditions text; the coverage audit's Sucuri wall did not reproduce for our agent.",
    ),
    where=(
        "https://adk.org/explore/high-peaks-conditions-report/",
        "https://adk.org/terms-conditions/",
        "https://nptrail.org/current-trail-conditions/",
    ),
    terms='https://adk.org/terms-conditions/ ("Last updated August 12, 2026"), §3 User Representations: "By using the Services, you represent and warrant that: ... (5) you will not access the Services through automated or non-human means, whether through a bot, script or otherwise"; and under Prohibited Activities: "Except as may be the result of standard search engine or Internet browser usage, use, launch, develop, or distribute any automated system, including without limitation, any spider, robot, cheat utility, scraper, or offline reader that accesses the Services, or use or launch any unauthorized script or other software." and "Engage in any automated use of the system, such as using scripts to send comments or messages, or using any data mining, robots, or similar data gathering and extraction tools."',
    reason="refused: ADK's terms forbid access through automated or non-human means (quoted in `terms`); held until ADK permits, recorded as decision 47 records ATC's",
)
