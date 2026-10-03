"""Ozark Highlands Trail Association: closures, from the club's trail-alerts page and its Trail Alerts posts,
hourly (decision 53 phase B, 2026-10-03).

Read live under our agent on 2026-10-03 after ozarkhighlandstrail.com's robots.txt (WooCommerce paths
and /wp-admin/ only, no Crawl-delay):

- `ohta_trail_alerts`: the live channel, WordPress page 2987 ('Trail Alerts'), read through its REST
  route `/wp-json/wp/v2/pages/2987`, which carries no query string, as one PageNotice
  (extract/_notices.py's `wp_page`). It held two sections that day, 'Bridge & Trailhead Closure' (the
  Big Piney Creek bridge at mile 103.9, closed until December 3, 2026) and 'Road Closure', and is
  dated by its own modified_gmt, 2026-09-22.
- `ohta_trail_alerts_posts`: the 'Trail Alerts' category (id 18, slug 'trailalerts'), 14 posts by
  X-WP-Total, through WordpressPosts. DORMANT: the newest was modified 2022-03-04 ('Prescribed Burn
  near Richland Creek'), so it is dated history. Its posts' `content` and `excerpt` never load:
  they carried a maintenance e-mail address and a telephone number that day (decision 59; the row's
  person_fields). The category feed (/category/trailalerts/feed/) is a window of the same list and is
  not read.

The page's sections are closures and warnings both, split in dbt (decision 7), so warnings.py shares
this file. The live burns for the Ozark-St Francis come from usfs/warnings.py's prescribed-burn layer.

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c8_regional_5), whose `checked` read: "`/trail-alerts/` (WP page, `modified` 2026-09-21): 'The bridge
over Big Piney Creek (mm 103.9) is closed for a rehabilitation project. Work is expected to continue
until December 3, 2026'; 'Fort Douglas trailhead (mm 103.7) … may be inaccessible'; 'East Fly Gap Road is
closed … due to a landslide'. The WP category 'Trail Alerts' (id 18) has 14 posts, newest 2022-03-04."
"""

from extract._kinds import page_notice, wordpress_posts

CLAIMS = ("ohta_trail_alerts", "ohta_trail_alerts_posts")
RESOURCES = [page_notice("ohta_trail_alerts", wp_page=2987), wordpress_posts("ohta_trail_alerts_posts")]
