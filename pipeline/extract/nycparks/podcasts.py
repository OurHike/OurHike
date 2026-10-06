"""NYC Parks: podcasts, 1 feed read here (decision 54 wave 3, section C, 2026-10-04).

- `nycparks_covid_oral_history_podcast`: NYC Parks Covid Oral History, on blubrry.net: 10 episodes,
  2023-05-16 to 2023-08-08. The feed's host is not nycgovparks.org, whose robots.txt (`Disallow:
  /*json`) refuses that host's JSON only.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.
"""

from extract._content import podcast_episodes

CLAIMS = ("nycparks_covid_oral_history_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
