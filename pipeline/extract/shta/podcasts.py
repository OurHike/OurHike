"""Superior Hiking Trail Association: podcasts, 1 feed read here (decision 54 wave 3, section C,
2026-10-04).

- `shta_blazing_trail_podcast`: Blazing Trail: 40 Years on the Superior Hiking Trail, SHTA's with
  WTIP, on transistor.fm: 12 episodes, 2025-12-22 to 2026-08-14, its <copyright> 'WTIP, 2026'.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Superior Hiking Trail Association: podcasts, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

RSS. The SHTA's own. Skeptic: confirmed. `<itunes:author>` is "Superior Hiking Trail Association,
WTIP", and the description reads "a special-edition podcast created by WTIP and the Superior Hiking
Trail Association". The first `<item>`'s pubDate is 2026-08-14. (M)

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Blazing Trail: 40 Years on the Superior Hiking Trail" (SHTA
with WTIP), linked from `/40th-anniversary/`. RSS `https://feeds.transistor.fm/blazing-trails`, 12
episodes, latest 2026-08-11.

Its `where`: https://feeds.transistor.fm/blazing-trails

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("shta_blazing_trail_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
