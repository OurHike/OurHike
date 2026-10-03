"""Colorado Trail Foundation: warnings, behind a wall that refuses our agent (decision 53 phase B,
2026-10-03).

coloradotrail.org answered HTTP 403 with SiteDistrict's WAF page to the decision 53 inventory (batch
3, 2026-10-03), for its closures feed (https://coloradotrail.org/category/closures/feed/), its
alerts page (https://coloradotrail.org/traveling-the-ct/alerts/) and its robots.txt alike: "Your
access to this page has been blocked. Your request appears similar to malicious requests sent by
robots." The page echoed 'ASN: ANTHROPIC' and our User-Agent, so the block may be by network rather
than by agent (Reasoned). Nothing was retried and no other header was tried (decision 39). Whether a
GitHub-hosted runner, on another network, is let through is the open question; until it is answered,
or the CTF permits, nothing is fetched. The audit's WordPress category 'closures' and Google My Map
of obstructions are behind the same wall.

Before decision 53 phase B, 2026-10-03, this note read:

Colorado Trail Foundation: warnings, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Its water-source half is drought/water conditions, which decision 2 keeps out of `warnings`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The same alerts map (obstructions). The post "2026 Wildfires,
Water Sources, and Snowpack Outlook" ("extreme fire danger").

Its `where`: https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services
https://coloradotrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        '(the decision 53 inventory, batch 3, 2026-10-03) https://coloradotrail.org/category/closures/feed/, https://coloradotrail.org/traveling-the-ct/alerts/ and https://coloradotrail.org/robots.txt: each HTTP 403, SiteDistrict WAF: "Your access to this page has been blocked. Your request appears similar to malicious requests sent by robots."',
    ),
    where=(
        "https://coloradotrail.org/category/closures/feed/",
        "https://coloradotrail.org/traveling-the-ct/alerts/",
        "https://coloradotrail.org/robots.txt",
    ),
    reason="unreadable: the host answers our named agent with a 403 WAF wall, never worked round (decision 39); held until a CI runner is let through or the CTF permits",
)
