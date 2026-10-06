"""USDA Forest Service: podcasts, 2 feeds read here (decision 54 wave 3, section C, 2026-10-04).

- `usfs_forest_focus_podcast`: Forest Focus, the Pacific Southwest Region's show on libsyn: 38
  episodes, 2022-09-06 to 2024-12-21.
- `usfs_forestcast_podcast`: Forestcast, the research show on libsyn: 36 episodes, 2020-02-24 to
  2024-12-18, its <copyright> 'Public Domain'. Every episode note carries one named staff member's
  e-mail address, so its prose columns never load (decision 59).

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

USDA Forest Service: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Forest Focus includes a trail-crew episode ("Trails in Transformation", search). "Forest North" is
the Ely Tourism Bureau's show, not USFS's.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Forest Focus (USDA Forest Service, Pacific Southwest Region):
`https://rss.libsyn.com/shows/433686/destinations/3617892.xml`, 38 episodes, newest 2024-12-21.
Forestcast (research): `https://rss.libsyn.com/shows/184682/destinations/1267985.xml`, 36 episodes,
newest 2024-12-18. Custer Gallatin "Forest in Focus"
(`fs.usda.gov/r01/custergallatin/multimedia/audio`, search).

Its `where`: https://rss.libsyn.com/shows/433686/destinations/3617892.xml
https://rss.libsyn.com/shows/184682/destinations/1267985.xml
https://fs.usda.gov/r01/custergallatin/multimedia/audio

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("usfs_forest_focus_podcast", "usfs_forestcast_podcast")
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
