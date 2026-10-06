"""The Cohos Trail Association: closures, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `cohos_trail_changes`: Cohos Trail: Trail Changes and Updates, one notice, WordPress page 66
  through its REST route (PageNotice). Reroutes and removed structures (Baldhead Shelter removed
  2025, the 2022 Coleman State Park reroute), read through WordPress page 66. Some of its text is
  years old, so what the notice carries is the page's own date.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import page_notice

CLAIMS = ("cohos_trail_changes",)
RESOURCES = [page_notice("cohos_trail_changes", wp_page=66)]
