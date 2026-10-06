"""Appalachian Mountain Club: podcasts, 1 feed read here (decision 54 wave 3, section C, 2026-10-04).

- `amc_unlikely_stories_podcast`: Unlikely Stories Podcast, on simplecast: 11 episodes, 2021-08-24
  to 2021-10-27, its <copyright> 'Appalachian Mountain Club'. not_available.toml [amc_at.podcasts] draws it from here
  (decision 34). Its itunes:author names each episode's guests and its RSS <author> is an e-mail
  address, so both are left out; the episode titles name the guest too ('Superhuman Hiker | …'), and
  a title is kept, being the episode's published name.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.
"""

from extract._content import podcast_episodes

CLAIMS = ("amc_unlikely_stories_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
