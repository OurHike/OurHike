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

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

AMC Delaware Valley Chapter: warnings, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Dormant: one post, 2023. Lehigh Gap is in `kta`'s A.T. section, not AMC-DV's, so a row from here has
to be deduplicated against KTA and ATC in dbt. ATC's own "George W. Outerbridge Shelter Yearly Bear
Warning" covers the same area.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): WP REST post "Bear Safety",
`https://amcdv.org/activities/bear-safety/` (2023-07-05; categories activities, conservation,
state-forests, state-parks, trail-work): "The current hot spot seems to be around Lehigh Gap, where
there have been several bear sighting on or near the A.T. over the past several weeks", with PA Game
Commission / BearWise flyers. Readable through `/wp-json/wp/v2/posts`.
`/leadership/pennsylvania-state-game-lands-special-use-permit-requirements/` covers group-permit
procedure, not hunting-season notices.

Its `where`: https://amcdv.org/activities/bear-safety/ https://amcdv.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("amcdv_bear_safety",)
RESOURCES = [page_notice("amcdv_bear_safety", wp_post=5079)]
