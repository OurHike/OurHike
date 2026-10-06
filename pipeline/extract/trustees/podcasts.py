"""The Trustees of Reservations: podcasts, 1 feed read here (decision 54 wave 3, section C,
2026-10-04).

- `trustees_on_the_coast_podcast`: Trustees On The Coast, on anchor.fm: 2 episodes, both 2025-03-27.
  The show's page, www.onthecoast.thetrustees.org/podcast, was not read (the coverage audit's proxy
  refused it). The deCordova sculpture audio tours run in the OnCell app and are not trail content.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.
"""

from extract._content import podcast_episodes

CLAIMS = ("trustees_on_the_coast_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
