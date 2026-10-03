"""Friends of the Blue Hills: closures, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Low volume and mixed with news. DCR's own mass.gov alerts are the manager's channel; I did not check
them. Skeptic: `https://www.mass.gov/locations/blue-hills-reservation` answers 403 to curl
(2026-10-01), so DCR's alerts are UNKNOWN, not absent. They belong to a DCR folder in any case. FBH
has no …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.mass.gov/alerts/page/14961 (html_page);
https://www.mass.gov/locations/blue-hills-reservation (html_page);
https://friendsofthebluehills.org/feed/ (rss);
https://friendsofthebluehills.org/wp-json/wp/v2/categories?per_page=100&_fields=id,name,slug,count
(wordpress).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'FBH WordPress posts (`/wp-json/wp/v2/posts`, `/feed/` is RSS): "TRAIL ALERT!! St. Moritz Ponds Area of'
        ' the Park", "Eliot Tower Closed for Restoration".',
    ),
    where=(
        "https://www.mass.gov/locations/blue-hills-reservation",
        "https://mass.gov",
        "https://friendsofthebluehills.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
