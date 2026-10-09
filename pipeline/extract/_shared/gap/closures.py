"""Great Allegheny Passage Conservancy: closures, held. A candidate steward with no trail_orgs.json row yet, so it
lives in _shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every
type, held"). Held until the maintainer approves the conservancy's trail_orgs.json row in chat (decision 121);
then this file moves to the club folder of the same name.

- `gap_trail_alerts`: the site's `trail-alerts` post type, read whole through its REST route (65 posts on
  2026-10-09), each with the conservancy's own status (Cleared, Partially Obstructed or Fully Obstructed) and a
  place (latitude, longitude and mile marker) in its ACF fields. gaptrail.org's robots.txt asks no Crawl-delay
  and allows the route (2026-10-09).
"""

from extract._kinds import wordpress_posts

TYPE = "closures"
CLAIMS = ("gap_trail_alerts",)
RESOURCES = [wordpress_posts("gap_trail_alerts", post_type="trail-alerts")]
