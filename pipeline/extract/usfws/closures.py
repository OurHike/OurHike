"""US Fish & Wildlife Service: closures, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Page, scraped per refuge (about 570). The `fws-sync-trails` block name suggests trail alerts join to
the trails inventory (Reasoned). If so, closures could land on segments. Nobody has confirmed it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

NOT WIRED IN DECISION 53 PHASE B (2026-10-03), AND WHY: cost, not access. fws.gov serves our agent
(200, the inventory, batch 5), and its robots.txt's `User-agent: *` group disallows Drupal defaults,
`*page=` and facet URLs only. But the alerts live one refuge homepage at a time: 591 refuge homepages
in refuges-and-fws-offices/sitemap.xml, each 100 KB or more (Blackwater's 116,359 bytes), so a full
pass is 591 requests, two seconds apart at least: about 20 minutes, against a conditions leg's
150-second read budget. Reading one refuge, Blackwater, because it was the sample, would be a guess
at which refuge matters. What settles it is a reviewed list of the refuges the build's trails cross,
each then its own registry row (a few at a time on the hourly lane), or a daily rotation; both are
decision 53 phase F's budget question (@unvalidated). The refuge's Drupal ETag and Last-Modified are
page-cache stamps and would not decide FRESH. Blackwater on 2026-10-03: 1 alert (critical, node
5399876, '2026-27 Hunt Closures': Wildlife Drive closed 2026-10-22, 10-23, 12-04 and 2027-01-08) and 4
empty `trail_alert` displays.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(decision 53 inventory, batch 5, 2026-10-03) https://www.fws.gov/refuge/blackwater: 200 to our agent, "
        "116,359 bytes, 1 alert (critical, node 5399876); https://www.fws.gov/refuges-and-fws-offices/sitemap.xml: 867 "
        "URLs, 591 refuge homepages.",
        "Each refuge homepage on fws.gov (Drupal) renders an alert view, `view-id-alert`, beside a "
        "`block-fws-facility-trail-alerts` block driven by a `trail_alert` display. Example, read today: "
        '`https://www.fws.gov/refuge/blackwater`, "2026-27 Hunt Closures … Wildlife Drive will be CLOSED on … '
        'October 22, 2026…". `/alerts` and `/jsonapi` both 404. `sitemap.xml` is an index including '
        "`refuges-and-fws-offices/sitemap.xml`. Skeptic spot check (2026-10-01): Blackwater's `view-id-alert` "
        'block still reads "2026-27 Hunt Closures … majority of Wildlife Drive will be CLOSED … Thursday, '
        "October 22, 2026 … Some …",
    ),
    where=(
        "https://www.fws.gov/refuge/blackwater",
        "https://www.fws.gov/refuges-and-fws-offices/sitemap.xml",
        "https://fws.gov",
    ),
    reason=(
        "published and not landed: 591 refuge pages are not an hourly read, and which refuges the build's "
        "trails cross is a list nobody has reviewed yet"
    ),
)
