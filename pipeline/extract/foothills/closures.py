"""Foothills Trail Conservancy: closures, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

No year is printed on the 4/13 and 3/23 entries. 2025 follows from their order. There is no feed.
The site `/feed/` has 9 posts, newest 2022-11-22, none of them closures. (Skeptic, re-read
2026-10-01: same three entries. The 3/23 fire closure ends "(See post on Facebook)", so the club's
Facebook …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/trail-conditions/`, a hand-edited HTML page. The newest entry, "Trail Update 4/13", says the entire '
        'trail is open. Below it is "Critical fire update 3/23", which closed Sassafras→Table Rock SP and '
        'Sassafras→Caesars Head SP. Then "Update Mar 12, 2025" on reopening after Helene.',
    ),
    where=("https://foothillstrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
