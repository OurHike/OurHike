"""Randolph Mountain Club: closures, published, and not landed (coverage audit 2026-10-01, batch
p05_persist).

Federal page. USFS work is public domain under 17 U.S.C. 105, the `usfs_licence` reading the
maintainer adopted 2026-09-02. Folder `usfs/` (the per-forest alerts scrape b6_federal.md item 8
describes).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.fs.usda.gov/r09/whitemountain/alerts` (Drupal HTML; Alerts Key Critical / Fire "
        'Restriction / Caution / Information) has 8 alerts. Examples: "Discovery Trail Emergency Closure" '
        '(Forest Order #09-22-02-26-05, 2026-08-31) and "Lincoln Woods Trail Closure" (June 15 through November'
        " 2026). None is in the northern Presidentials. No feed: `/r09/whitemountain/alerts/rss.xml` 404. "
        "`EDW_RecreationOpportunities_01.openstatus` for 0922: open 50, none 226, closed 0. Loaded ATC updates:"
        ' the nearest row, "Great Gulf: Bridge Closure" at 1873.8, is not on RMC\'s miles. Randolph Community '
        "Forest …",
    ),
    where=(
        "https://www.fs.usda.gov/r09/whitemountain/alerts",
        "https://randolphmountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
