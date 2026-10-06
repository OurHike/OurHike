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

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

NYC Parks: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

Dormant for three years and of no hiker value. Recorded so the next pass does not re-find it.
Loading it is the maintainer's call.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "NYC Parks Covid Oral History", artist "NYC Parks", feed
`https://nycparksoralhistory.blubrry.net/feed/podcast/`. 10 episodes, 2023-05-16 → 2023-08-08
(iTunes lookup `id1680243471`).

Its `where`: https://nycparksoralhistory.blubrry.net/feed/podcast/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("nycparks_covid_oral_history_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
