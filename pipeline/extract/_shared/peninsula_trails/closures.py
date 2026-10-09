"""Peninsula Trails Coalition: closures, held. A candidate steward with no trail_orgs.json row yet, so it lives in
_shared/ under the folder its row would name (decision 122, the maintainer's poll, 2026-10-09: "Every type, held").
Held until the maintainer approves the coalition's trail_orgs.json row in chat (decision 121); then this file moves
to the club folder of the same name.

- `odt_trail_alerts_feed`: the Olympic Discovery Trail's 'Trail Alerts' post type as RSS, 4 items on 2026-10-09.
  The post type has no REST route, so the feed is its only list; a feed is a window, never read as lifted.
  olympicdiscoverytrail.org's robots.txt asks no Crawl-delay (2026-10-09).
"""

from extract._notices import feed_notices

TYPE = "closures"
CLAIMS = ("odt_trail_alerts_feed",)
RESOURCES = [feed_notices("odt_trail_alerts_feed")]
