"""US Fish & Wildlife Service: closures, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

Page, scraped per refuge (about 570). The `fws-sync-trails` block name suggests trail alerts join to
the trails inventory (Reasoned). If so, closures could land on segments. Nobody has confirmed it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.fws.gov/refuge/blackwater (html_page).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
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
        "https://fws.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
