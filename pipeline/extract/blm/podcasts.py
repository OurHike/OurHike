"""Bureau of Land Management: podcasts, 1 feed read here (decision 54 wave 3, section C, 2026-10-04).

- `blm_on_the_ground_podcast`: On the Ground, on blm.gov: 26 episodes, 2024-05-16 to 2025-09-24. A
  federal work, public domain on 17 U.S.C. 105. The coverage audit's other two shows, Alaska
  Frontiers and Your American Lands, were found by search and have no feed URL read yet.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Bureau of Land Management: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Programming, not trail audio.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "On the Ground": `https://www.blm.gov/media/podcasts/otg.rss`,
26 items with enclosures, newest 2025-09-24. Also Alaska Frontiers and Your American Lands
(`blm.gov/media/podcasts/…`, search).

Its `where`: https://www.blm.gov/media/podcasts/otg.rss https://blm.gov/media/podcasts/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("blm_on_the_ground_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
