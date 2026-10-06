"""NYS DEC: podcasts, 1 feed read here (decision 54 wave 3, section C, 2026-10-04).

- `dec_does_what_podcast`: DEC Does What?!, DEC's own show on podbean: 39 episodes, 2024-04-03 to
  2026-08-05. Its <copyright> reads 'Copyright 2025 All rights reserved.', which restricts reuse and
  refuses no reading; publication is decided in dbt.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.
"""

from extract._content import podcast_episodes

CLAIMS = ("dec_does_what_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
