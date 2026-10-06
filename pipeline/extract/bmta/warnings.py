"""Benton MacKaye Trail Association: warnings, 1 notice source read here (decision 53 phase B,
2026-10-03).

- `bmta_alert_bar`: BMTA site alert bar, one notice for the page (PageNotice, region
  `.alert-bar__content`). The site-wide alert bar on bmta.org's home page, read alone
  (`div.alert-bar__content`). bmta.org asks `Crawl-delay: 60`, one request an hour at most. The bar
  disagreed with the PDF on 2026-10-03 (a GSMNP park-wide fire ban the PDF calls 'Cancelled' and
  NPS's alerts do not carry), so neither publishes as current without NPS's alerts beside it.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("bmta_alert_bar",)
RESOURCES = [page_notice("bmta_alert_bar", region=".alert-bar__content", crawl_delay=60.0)]
