"""Sierra Buttes Trail Stewardship: podcasts, 1 feed read here (decision 54 wave 3, section C,
2026-10-04).

- `sbts_dirt_magic_podcast`: Dirt Magic, on buzzsprout: 40 episodes, 2023-03-02 to 2026-09-04. 16
  are short 'Dirt Magic Trails Report' bulletins (the coverage audit): a trail report is a
  condition, and none of this row reaches a closure or a warning.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Sierra Buttes Trail Stewardship: podcasts, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

A real RSS feed. The trail-report episodes double as a conditions channel (see closures). Link the
audio, never copy it, under the copyright line.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Dirt Magic", RSS `https://rss.buzzsprout.com/1119050.rss`.
`itunes:author` is "Sierra Buttes Trail Stewardship", hosted by a named individual. 40 episodes,
2023-03-02 → 2026-09-04. Copyright "© 2026 Dirt Magic". Found through the Apple directory
(`itunes.apple.com/search?media=podcast&term=Sierra Buttes Trail Stewardship`, 1 result). 16 of the
40 are short "Dirt Magic Trails Report" bulletins, 2025-12-05 → 2026-09-04, near-weekly from March
to May 2026.

Its `where`: https://rss.buzzsprout.com/1119050.rss
https://itunes.apple.com/search?media=podcast&term=Sierra

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("sbts_dirt_magic_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
