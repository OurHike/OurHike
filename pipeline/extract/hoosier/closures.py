"""Hoosier Hikers Council: closures, unreadable: the council's robots.txt resets the connection
(decision 53 phase B, 2026-10-03).

The council's trail-conditions feed
(https://www.hoosierhikerscouncil.org/category/trail-conditions/feed/) answered 200 to the decision
53 inventory (batch 2), but its robots.txt reset the connection then and again at
2026-10-03T22:00:40Z, and RFC 9309 reads an unreachable robots.txt as complete disallow, so nothing
is fetched. The feed was dormant anyway: 6 items, the newest 'Second Knobstone Trail Closure',
2023-11-14. The live Knobstone source is Indiana DNR's conditions page
(https://www.in.gov/dnr/forestry/properties/knobstone-trail-conditions-reroutes-maps/, 'Knobstone
Trail conditions Update: July 21, 2026', 'TRAIL CONDITION: GOOD'), a steward with no club folder, so
it is read once in _shared/in_dnr/ as `in_dnr_knobstone_conditions` (decision 34). IN.gov's terms
restrict reuse to personal use and name bots among 'disruptive activities' (quoted in `checked`): a
restriction on copying and on disruptive use, not on reading, which is decision 55's reading and the
maintainer's to confirm.

Before decision 53 phase B, 2026-10-03, this note read:

Hoosier Hikers Council: closures, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

The feed's last item is 23 months old, so it can carry dated history but cannot say "no closures
now". For the Knobstone, the DNR page is the live source. (Skeptic correction, 2026-10-01: the two
DNR PDFs are not current. In the page's HTML both links sit inside an HTML comment ( …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): WordPress category RSS
`https://www.hoosierhikerscouncil.org/category/trail-conditions/feed/`: 6 items, newest 2023-11-14
("Second Knobstone Trail Closure"), oldest 2018-01-29. The Tecumseh page has a reroute notice and
`/assets/Tecumseh_Trail_Reroute_202206.pdf`. Upstream: IN DNR
`https://www.in.gov/dnr/forestry/properties/knobstone-trail-conditions-reroutes-maps/` links closure
and reroute PDFs (`fo-Knobstone-Trail-closure.pdf`, `fo-Knobstone-Trail-reroute-112023.pdf`).

Its `where`: https://www.hoosierhikerscouncil.org/category/trail-conditions/feed/
https://www.in.gov/dnr/forestry/properties/knobstone-trail-conditions-reroutes-maps/
https://hoosierhikerscouncil.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(the decision 53 inventory, batch 2, 2026-10-03) https://www.hoosierhikerscouncil.org/robots.txt: connection reset (curl 35); the feed answered 200 seconds earlier, 6 items, newest 2023-11-14; /wp-json/ also reset.",
        "https://www.hoosierhikerscouncil.org/robots.txt re-read at 2026-10-03T22:00:40Z under lib/user_agent.py's agent: 'Connection reset by peer' again, so the feed was not requested.",
        "(the inventory, batch 2) https://www.in.gov/dnr/forestry/properties/knobstone-trail-conditions-reroutes-maps/: 200, its own 'Update: July 21, 2026' and 'TRAIL CONDITION: GOOD'; www.in.gov's robots.txt holds only a Sitemap line. Its terms: https://www.in.gov/core/terms_of_use.html: \"No part of any content, graphic, form, or document may be reproduced in any form or incorporated into any information retrieval system, electronic or mechanical, other than for your personal use (not for resale or redistribution).\" And, under Prohibited Behavior: \"You are prohibited from using the Portal in any way to do any of the following: … engage in disruptive activities online, including excessive use of scripts, sound waves, scrolling (repeating the same message over and over), or use viruses, bots, worms, or trojan horses\"",
    ),
    where=(
        "https://www.hoosierhikerscouncil.org/category/trail-conditions/feed/",
        "https://www.in.gov/dnr/forestry/properties/knobstone-trail-conditions-reroutes-maps/",
        "https://www.in.gov/core/terms_of_use.html",
    ),
    reason="unreadable: robots.txt is unreachable, which RFC 9309 reads as disallow; Indiana DNR's Knobstone page is _shared/in_dnr/'s `in_dnr_knobstone_conditions`",
    recheck_after_days=30,
)
