"""Cumberland Valley Appalachian Trail Club: closures, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

This is a general news feed and the yield is low. Items need classifying, and an unclassified item
goes to warnings (decision 7).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "News RSS `https://www.cvatclub.org/news/feed` (Weebly RSS 2.0, 10 items, 2020-09 → 2026-09). One "
        'reroute in it: 2023-07-15, a temporary bridge and reroute "approximately one half mile north of the '
        'Scott Farm"',
    ),
    where=("https://www.cvatclub.org/news/feed",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
