"""Monadnock-Sunapee Greenway Trail Club: closures, 1 notice source read here (decision 53 phase B,
2026-10-03).

- `msgtc_trail_conditions`: MSGTC Trail Conditions, one notice, WordPress page 24 through its REST
  route (PageNotice). One page of dated condition entries and a standing relocation notice
  (Stoddard, effective November 2020), read through WordPress page 24 on www.msgtc.org, the host
  msgtc.org redirects to. Both hosts ask `Crawl-delay: 10`.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Monadnock-Sunapee Greenway Trail Club: closures, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/trail-conditions/`: dated entries (April 2026, "entire 48.7
miles … swept, cleared"), plus a relocation notice in Stoddard with a "Download Relocation Map"
link.

Its `where`: https://msgtc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("msgtc_trail_conditions",)
RESOURCES = [page_notice("msgtc_trail_conditions", wp_page=24, crawl_delay=10.0)]
