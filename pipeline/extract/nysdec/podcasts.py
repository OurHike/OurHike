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

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

DEC's own show, 'DEC Does What?!', not landed: its feed reads 'All rights reserved', and episodes
would be linked, not re-hosted.

Its `checked` (confirmed 2026-10-01): the show's RSS feed: 39 episodes, a few about trails (Forest
Rangers, camping, the hunting season) reference/podcast_episodes.json: no episode of it

Its `where`: https://feed.podbean.com/Multimedia3/feed.xml

Its `terms`: the feed's <copyright>: "Copyright 2025 All rights reserved."

Its `reason`: not landed: an episode list is editorial, picked per hike in _shared/podcasts/
"""

from extract._content import podcast_episodes

CLAIMS = ("dec_does_what_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
