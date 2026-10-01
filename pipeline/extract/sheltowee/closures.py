"""Sheltowee Trace Association: closures, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The page is live, but the RSS is not: the Alert-category feed has 1 item, from 2021-03-28. Read the
page, not the feed. Skeptic, re-read 2026-10-01: the tornado closure, the Red River and Blue Herron
items are all still there. The "Trail Conditions" category feed …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/alerts`: "Spring Tornado Closes Trace From Highway 80 to Highway 192" ("Far Out Miles (Southbound) '
        'Highway 80 Mile 183.9 to Highway 192 Mile 201.4 are CLOSED … This is a 2-year projected closing"); '
        '"Blue Herron Bridge Closure" ("Tipple Bridge has been closed … The closure is indefinite"); "Red River'
        ' Suspension Bridge … inaccessible". 5 linked items in all.',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://sheltoweetrace.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
