"""Sierra Buttes Trail Stewardship: closures, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

A page, not machine-readable. Squarespace's `robots.txt` disallows `?format=json`, so a parser must
read the HTML. Only "CLEAR" appears today, so the word a closed trail would get is unseen (Reasoned:
it would be a non-CLEAR word). Mountain-bike-first, but the Mt. Hough network is "open to all …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "~~No conditions page among the 171 sitemap URLs.~~ That holds for sierratrails.org only. "
        '`https://www.yubaexpeditions.com/trail-conditions` (HTML, Squarespace). Its about page says "We are an'
        ' extension of the NON-Profit Sierra Buttes Trail Stewardship", and the footer reads "Copyright © 2025 '
        'Sierra Buttes Trail Stewardship. All Rights Reserved." It lists 40 named trails, each with a status '
        "word: Mt. Hough / Quincy 19, Downieville 14, Mills Peak and Lakes Basin 7. Every network block is "
        'stamped "Updated 9/4/26". There are also 6 highway and county-road statuses, "Updated 5/29/26". The '
        "page …",
    ),
    where=(
        "https://www.yubaexpeditions.com/trail-conditions",
        "https://sierratrails.org",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
