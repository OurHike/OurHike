"""Superior Hiking Trail Association: podcasts, 1 feed read here (decision 54 wave 3, section C,
2026-10-04).

- `shta_blazing_trail_podcast`: Blazing Trail: 40 Years on the Superior Hiking Trail, SHTA's with
  WTIP, on transistor.fm: 12 episodes, 2025-12-22 to 2026-08-14, its <copyright> 'WTIP, 2026'.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.
"""

from extract._content import podcast_episodes

CLAIMS = ("shta_blazing_trail_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
