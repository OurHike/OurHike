"""Colorado Parks & Wildlife (COTREX): podcasts, 1 feed read here (decision 54 wave 3, section C,
2026-10-04).

- `cpw_colorado_outdoors_podcast`: Colorado Outdoors, the Podcast for Colorado Parks and Wildlife,
  on art19: 54 episodes, 2020-10-22 to 2026-10-01, linked from cpw.state.co.us/CPW-podcast.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Colorado Parks & Wildlife — COTREX: podcasts, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Active.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Colorado Outdoors – the Podcast for Colorado Parks and
Wildlife": RSS `https://rss.art19.com/colorado-outdoors`, 54 episodes, latest 2026-10-01 (iTunes
lookup, id 1537137938). Page: `cpw.state.co.us/CPW-podcast`.

Its `where`: https://rss.art19.com/colorado-outdoors https://cpw.state.co.us/CPW-podcast

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("cpw_colorado_outdoors_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
