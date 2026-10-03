"""Friends of the Blue Hills: closures, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Low volume and mixed with news. DCR's own mass.gov alerts are the manager's channel; I did not check
them. Skeptic: `https://www.mass.gov/locations/blue-hills-reservation` answers 403 to curl
(2026-10-01), so DCR's alerts are UNKNOWN, not absent. They belong to a DCR folder in any case. FBH
has no …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

DCR's notices for the reservation are mass.gov's per-park alerts fragment
(https://www.mass.gov/alerts/page/14961, the node the park page
https://www.mass.gov/locations/blue-hills-reservation loads; 1 item on 2026-10-03, an event notice
'Updated Sep. 24, 2026'). It is DCR's, read once in _shared/ma_dcr/ as `ma_dcr_blue_hills_alerts`
(decision 34). mass.gov's terms ("the Commonwealth forbids any copying or use other than 'fair
use'") restrict copying, not reading: decision 55's case. Friends of the Blue Hills' WordPress has
13 categories and none for closures or alerts, so its feed (https://friendsofthebluehills.org/feed/)
is not read: choosing its 'TRAIL ALERT!!' posts out of the blog would be prose parsing.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        'FBH WordPress posts (`/wp-json/wp/v2/posts`, `/feed/` is RSS): "TRAIL ALERT!! St. Moritz Ponds Area of the Park", "Eliot Tower Closed for Restoration".',
    ),
    where=(
        "https://www.mass.gov/locations/blue-hills-reservation",
        "https://mass.gov",
        "https://friendsofthebluehills.org/",
        "https://www.mass.gov/alerts/page/14961",
    ),
    reason="drawn from _shared/ma_dcr/'s `ma_dcr_blue_hills_alerts`, extracted once there (decision 34); the Friends' blog has no notice category",
)
