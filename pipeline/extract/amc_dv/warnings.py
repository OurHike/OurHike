"""AMC Delaware Valley Chapter: warnings, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `amcdv_bear_safety`: AMC Delaware Valley Chapter: Bear Safety, one notice, WordPress post 5079
  through its REST route (PageNotice). The chapter's one warnings post, dated 2023-07-05: its
  'current hot spot' at Lehigh Gap was written three years ago, so it publishes beside its own date
  or not at all.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("amcdv_bear_safety",)
RESOURCES = [page_notice("amcdv_bear_safety", wp_post=5079)]
