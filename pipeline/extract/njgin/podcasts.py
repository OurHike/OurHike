"""NJDEP / NJGIN: podcasts, 1 feed read here (decision 54 wave 3, section C, 2026-10-04).

- `njdep_discover_dep_podcast`: Discover DEP, the Official Podcast of the NJ Department of
  Environmental Protection, on podbean: 95 episodes, 2016-04-21 to 2018-05-01. Its episode notes
  carry named staff members' own e-mail addresses and telephone numbers, so its prose columns never
  load (decision 59).

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

NJDEP / NJGIN — Statewide Trails: podcasts, published, and not landed (coverage audit 2026-10-01,
batch b5_nyc_nj_ct_ma_pa).

Dormant for 8 years. Low value.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Discover DEP: the Official Podcast of the NJ Department of
Environmental Protection", feed `https://feed.podbean.com/njdep/feed.xml` (200, 392,517 bytes). 95
episodes, 2016-04-21 → 2018-05-01. 12 titles mention trail, park, hike, bear, fire or forest (iTunes
`id1109394162`).

Its `where`: https://feed.podbean.com/njdep/feed.xml

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("njdep_discover_dep_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
