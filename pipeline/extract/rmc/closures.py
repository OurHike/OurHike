"""Randolph Mountain Club: closures, drawn from usfs/closures.py's White Mountain National Forest alerts page
(decision 53 phase B, 2026-10-03).

RMC publishes no closures of its own (decision 53's inventory, batch 4). The White Mountain National
Forest's alerts page is the Forest Service's, so it lands once, in usfs/closures.py as
`usfs_r09_whitemountain_alerts` (decision 34), and RMC's portion is assigned in dbt.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
p05_persist): "Federal page. USFS work is public domain under 17 U.S.C. 105 ... Folder `usfs/`", whose
`checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "usfs/closures.py `usfs_r09_whitemountain_alerts` reads https://www.fs.usda.gov/r09/whitemountain/alerts "
        "(decision 53 phase B, 2026-10-03): 8 alert cards, fire-restriction 1, caution 5, information 2.",
        "(coverage audit, 2026-10-01) `https://www.fs.usda.gov/r09/whitemountain/alerts` (Drupal HTML; Alerts Key "
        'Critical / Fire Restriction / Caution / Information) has 8 alerts. Examples: "Discovery Trail Emergency '
        'Closure" (Forest Order #09-22-02-26-05, 2026-08-31) and "Lincoln Woods Trail Closure" (June 15 through '
        "November 2026). None is in the northern Presidentials. No feed: `/r09/whitemountain/alerts/rss.xml` 404. "
        "`EDW_RecreationOpportunities_01.openstatus` for 0922: open 50, none 226, closed 0. Loaded ATC updates: the "
        'nearest row, "Great Gulf: Bridge Closure" at 1873.8, is not on RMC\'s miles. Randolph Community Forest …',
    ),
    where=(
        "https://www.fs.usda.gov/r09/whitemountain/alerts",
        "https://randolphmountainclub.org/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the page this org's closures arrive in",
)
