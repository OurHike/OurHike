"""Peninsula Trails Coalition: closures. The coalition's trail_orgs.json row, `peninsula-trails` (`load: via`, its line
RCO's), was approved on 2026-10-11 (decision 121, review page 02), so this file moved here from
_shared/peninsula_trails/, where decision 122 had loaded it held, and its raw table kept its name.

- `odt_trail_alerts_feed`: the Olympic Discovery Trail's 'Trail Alerts' post type as RSS, 4 items on 2026-10-09.
  The post type has no REST route, so the feed is its only list; a feed is a window, never read as lifted.
  olympicdiscoverytrail.org's robots.txt asks no Crawl-delay (2026-10-09).
"""

from extract._notices import feed_notices

CLAIMS = ("odt_trail_alerts_feed",)
RESOURCES = [feed_notices("odt_trail_alerts_feed")]
