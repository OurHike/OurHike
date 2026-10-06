"""The Cohos Trail Association: warnings, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `cohos_trouble_spots`: Cohos Trail: Trouble Spots, one notice, WordPress page 168 through its REST
  route (PageNotice). 'Trouble spots in 2026' by place (logging, Davis Path, Isolation Trail), read
  through WordPress page 168.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

The Cohos Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/trouble-spots/` (2026-07-13): "LOGGING. Active logging can
pose an extreme hazard to a hiker", by location.

Its `where`: https://cohostrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("cohos_trouble_spots",)
RESOURCES = [page_notice("cohos_trouble_spots", wp_page=168)]
