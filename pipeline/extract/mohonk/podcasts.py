"""Mohonk Preserve: podcasts, 1 feed read here (decision 54 wave 3, section C, 2026-10-04).

- `mohonk_walk_back_in_time_podcast`: Walk Back in Time, the Trapps Mountain Hamlet Path audio tour
  Mohonk links from its visit pages: 12 episodes, one a stop, all 2018-05-20, on Spreaker. Its
  <copyright> names one individual as the holder, not Mohonk; the name is a person's and is not
  copied into the registry row.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.
"""

from extract._content import podcast_episodes

CLAIMS = ("mohonk_walk_back_in_time_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
