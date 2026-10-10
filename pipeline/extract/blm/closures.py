"""Bureau of Land Management: closures, 1 ArcGIS layer extracted here (decision 53 phase B,
2026-10-03).

- `blm_or_rec_site_status`: BLM Oregon recreation site status,
  `OregonRecreationStatusWebmap20210428/FeatureServer/0`. Its row says why phase C should hold it
  back.

Each layer's row in sources.json holds its counts, dates, terms and the person fields it never
loads. Change checks are _kinds.py's ArcgisLayer: a conditional GET of the layer document on ArcGIS
Online, the statistics fingerprint on an on-prem server, and an allowed zero only beside the
server's own returnCountOnly read in the same run.

And 1 notice source read here (decision 53 phase B, 2026-10-03, pages, feeds and WordPress):

- `blm_alerts`: BLM Alerts, one notice for the page (PageNotice). blm.gov's national alerts view.
  Empty on 2026-10-03 ('No Results'), so its row is the page's own empty answer. Its Drupal ETag and
  Last-Modified are page-cache regeneration times, which moved overnight with no item on the page
  (the inventory), so they never decide FRESH.

blm.gov's Website Disclaimers (https://www.blm.gov/info/notices) carry no clause on automated
collection; every blm.gov path read here is allowed by its robots.txt for our agent, with no
Crawl-delay.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import arcgis_layer, page_notice

CLAIMS = ("blm_or_rec_site_status", "blm_alerts")
RESOURCES = [arcgis_layer("blm_or_rec_site_status"), page_notice("blm_alerts")]
