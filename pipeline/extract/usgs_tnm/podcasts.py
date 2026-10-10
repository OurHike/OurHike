"""USGS (The National Map): podcasts, 1 feed read here (decision 54 wave 3, section C, 2026-10-04).

- `usgs_outstanding_in_the_field_podcast`: Outstanding in the Field, on usgs.gov: 11 episodes,
  2018-12-10 to 2022-03-14. The coverage audit's skeptic found it answering only a browser's user
  agent; on 2026-10-04 it answered lib/user_agent.py's own agent 200, so nothing here imitates a
  browser (decision 39). Its itunes:author is a staff e-mail address on every item and its
  podcast:person names each guest, so both are left out. CoreCast, the former series, has no feed
  URL read.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.
"""

from extract._content import podcast_episodes

CLAIMS = ("usgs_outstanding_in_the_field_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
