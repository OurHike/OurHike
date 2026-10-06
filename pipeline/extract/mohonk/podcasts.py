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

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Mohonk Preserve: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

The audio tour is place-bound (12 stops on one Mohonk path), which is the shape a podcast mart
wants. It is Boulton's copyright, not Mohonk's. Metadata and links only. Skeptic spot-check: the
Spreaker feed answers 200 with 12 `<item>`s, "Stop 1: Boulder Pile in Old Pasture" to "Stop 12: Site
of the …

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/visit/the-trapps-mountain-hamlet-path-audio-tour/` links
Apple Podcasts `id1387239867`. The iTunes lookup gives "Walk Back in Time", feed
`https://www.spreaker.com/show/2957199/episodes/feed`: 12 episodes (one per stop), all 2018-05-20,
`<copyright>` "Copyright a named individual". Ridgelines 222 links a "Women in Wild Places"
partnership episode (`open.spotify.com/episode/4DwsE434kaBEn9vUycCkim`), a third party's show.
Neither is in `reference/podcast_episodes.json` (grep).

Its `where`: https://www.spreaker.com/show/2957199/episodes/feed
https://open.spotify.com/episode/4DwsE434kaBEn9vUycCkim https://mohonkpreserve.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("mohonk_walk_back_in_time_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
