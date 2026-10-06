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
"""

from extract._content import podcast_episodes

CLAIMS = ("blm_on_the_ground_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
