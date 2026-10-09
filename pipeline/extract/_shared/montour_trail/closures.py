"""Montour Trail Council: closures, held (decision 122; see points_of_interest.py beside this file).

- `montour_trail_alerts_page`: the 'Trail Alerts' page, one PageNotice read through WordPress's REST route (page
  6312, modified 2026-05-30), which names the National Tunnel (MM 25), closed indefinitely: the trail's longest
  closure, a banner the council's events feed does not carry. Read as HTML, the page's <article> leaves the banner
  out, so the REST record is what is read. montourtrail.org's robots.txt asks Crawl-delay 10, which the reader
  keeps; its title is held to 'Trail Alerts', so a reused page id is refused rather than read as the alerts.
"""

from extract._notices import page_notice

TYPE = "closures"
CLAIMS = ("montour_trail_alerts_page",)
RESOURCES = [page_notice("montour_trail_alerts_page", wp_page=6312, expect_title="Trail Alerts", crawl_delay=10)]
