"""NYNJTC's Trail Alerts: the category's posts, hourly, and the site's place terms, daily.

18 posts on 2026-10-01, the oldest from 2024-01-11, tagged from 186 terms
across `trail`, `park`, `region` and `state` (read live). The terms are their
own table, `raw_nynjtc__nynjtc_trail_alerts_terms`, because a renamed term
moves no post's `modified`; dbt resolves a post's ids against them, which
lib/nynjtc_alerts.py does at fetch today (ELT.md, "Source kinds").

`nynjtc_notices_licence` authorises publishing a post's headline, locality,
`modified` date and URL, never its body, which is NYNJTC's writing. The body
lands in the private raw store, as fetch_nynjtc_alerts.py caches it today,
and dbt's publication gate keeps it off a phone. Under decision 7 every post
reaches warnings as not reviewed until someone classifies whether it
obstructs the trail, which is why warnings.py shares this file.
"""

from extract._kinds import wordpress_posts, wordpress_terms
from lib.nynjtc_alerts import PLACE_TAXONOMIES

CLAIMS = ("nynjtc_trail_alerts",)
RESOURCES = [wordpress_posts("nynjtc_trail_alerts"), wordpress_terms("nynjtc_trail_alerts", PLACE_TAXONOMIES)]
