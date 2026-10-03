"""Florida Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://floridatrail.org/wp-json/wp/v2/posts?categories=37,40,41,42,43 (wordpress);
https://floridatrail.org/category/closures-and-nth-north/feed/ (rss);
https://floridatrail.org/hiker-safety/ (html_page).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'NTH posts in the same categories: "Free Bear Canisters Available… Ocala National Forest", "National '
        'Forest Bear Policy", "Camping Prohibited at Camp Blanding". Page '
        "`https://floridatrail.org/hiker-safety/`: static guidance on hunting season (links FWC season dates), "
        "named flood-prone rivers, and personal safety.",
    ),
    where=("https://floridatrail.org/hiker-safety/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
