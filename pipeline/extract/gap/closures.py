"""Great Allegheny Passage Conservancy: closures. The conservancy's trail_orgs.json row, `gap` (`load: via`, its line
PASDA's), was approved on 2026-10-11 (decision 121, review page 01), so this file moved here from _shared/gap/, where
decision 122 had loaded it held, and its raw table kept its name.

- `gap_trail_alerts`: the site's `trail-alerts` post type, read whole through its REST route (65 posts on
  2026-10-09), each with the conservancy's own status (Cleared, Partially Obstructed or Fully Obstructed) and a
  place (latitude, longitude and mile marker) in its ACF fields. gaptrail.org's robots.txt asks no Crawl-delay
  and allows the route (2026-10-09).
"""

from extract._kinds import wordpress_posts

CLAIMS = ("gap_trail_alerts",)
RESOURCES = [wordpress_posts("gap_trail_alerts", post_type="trail-alerts")]
