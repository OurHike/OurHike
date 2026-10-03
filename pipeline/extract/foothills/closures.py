"""Foothills Trail Conservancy: closures, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `foothills_trail_conditions`: Foothills Trail Conservancy Trail Conditions, one notice, WordPress
  page 25 through its REST route (PageNotice). One hand-edited page, read through WordPress page
  25's REST route: foothillstrail.org's robots.txt disallows every URL with a query string
  (`Disallow: /*?`) and asks `Crawl-delay: 10`. Its newest entry, 'Trail Update 4/13', carries no
  year, so the stated-date step is off (`date_pattern=None`) and the page's modified_gmt
  (2025-04-13) dates it: read on, the older 'Update Mar 12, 2025' would have dated the page a month
  early.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Foothills Trail Conservancy: closures, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

No year is printed on the 4/13 and 3/23 entries. 2025 follows from their order. There is no feed.
The site `/feed/` has 9 posts, newest 2022-11-22, none of them closures. (Skeptic, re-read
2026-10-01: same three entries. The 3/23 fire closure ends "(See post on Facebook)", so the club's
Facebook …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/trail-conditions/`, a hand-edited HTML page. The newest
entry, "Trail Update 4/13", says the entire trail is open. Below it is "Critical fire update 3/23",
which closed Sassafras→Table Rock SP and Sassafras→Caesars Head SP. Then "Update Mar 12, 2025" on
reopening after Helene.

Its `where`: https://foothillstrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("foothills_trail_conditions",)
RESOURCES = [page_notice("foothills_trail_conditions", wp_page=25, crawl_delay=10.0, date_pattern=None)]
