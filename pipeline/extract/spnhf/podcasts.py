"""Society for the Protection of NH Forests: podcasts, 1 feed read here (decision 54 wave 3, section C,
2026-10-04).

- `something_wild_podcast`: Something Wild, which NHPR introduces as "a joint production of NH
  Audubon, The Society for the Protection of New Hampshire Forests & NHPR", read from the feed
  Apple's directory gives for the show (id972135351, which NHPR's show page links): 116 episodes,
  2022-06-17 to 2026-10-02, its <copyright> '2023 New Hampshire Public Radio'. The Forest Society
  co-produces the show and does not hold it; no other folder draws on it, so it is extracted here
  (decision 34). Its itunes:author names the hosts on every item and is left out.

The rss.xml NHPR's page also links is a stale copy of the same show, noted in SAME_AS below and never
loaded: its 20 episodes, 2022-06-17 to 2023-03-24, are 20 of the live feed's 116, by guid and by
title (both read 2026-10-04).

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row, and the row's own
`person_fields`. The lane is the type's, monthly. Episodes are linked, never re-hosted. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Society for the Protection of NH Forests: podcasts, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

The feed is NHPR's and looks stale against the show. This belongs in `_shared/podcasts`, attributed
to its co-producers. Skeptic correction (M, 2026-10-01): the feed above is a dead copy. The live
feed is the one Apple's directory lists: …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Something Wild", which NHPR introduces as "a joint production
of NH Audubon, The Society for the Protection of New Hampshire Forests & NHPR". RSS:
`https://www.nhpr.org/podcast/something-wild/rss.xml` (20 items with enclosures; newest in the feed
is 2023-03-24; ©2026 NHPR). The SPNHF site has 166 `/something-wild/` transcript pages, the latest
dated 2026-09-17.

Its `where`: https://www.nhpr.org/podcast/something-wild/rss.xml https://forestsociety.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._content import podcast_episodes
from extract._contract import SameAs

CLAIMS = ("something_wild_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="something_wild_podcast",
        copy=("https://www.nhpr.org/podcast/something-wild/rss.xml",),
        confirmed=date(2026, 10, 4),
        checked=(
            "20 items, 2022-06-17 to 2023-03-24, every guid and every title one of the live feed's 116 "
            "(nhpr-rss.streamguys1.com/something_wild/something-wild-apple-podcasts.xml), both read 2026-10-04",
        ),
    ),
)
