"""Save Mount Diablo: podcasts, 1 feed read here (decision 54 wave 3, section C, 2026-10-04).

- `audible_mount_diablo_podcast`: Audible Mount Diablo, on libsyn: 209 episodes, 2019-02-01 to
  2026-08-27, its <copyright> 'Copyright 2019, Audible Mount Diablo - All Rights Reserved.' The
  show's producer is an individual and its sponsor the Mount Diablo Interpretive Association, in
  partnership with Save Mount Diablo (156 of 209 episode notes credit SMD). The coverage audit put
  it in _shared/podcasts/; it is extracted here instead, once, because neither the producer nor MDIA
  has a folder and this is the one folder that draws on it (decision 34).

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Save Mount Diablo: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

The feed is not on savemountdiablo.org, so SMD's no-automation terms do not govern it (Reasoned).
Its own "All Rights Reserved" does: link the episodes, never copy them. The producer is a named
individual and the sponsor is MDIA, so it belongs in `_shared/` podcasts (decision 12), with SMD's …

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Audible Mount Diablo", RSS
`https://rss.libsyn.com/shows/136346/destinations/844139.xml`. 209 episodes, 2019-02-01 →
2026-08-27. `itunes:author` is "a named individual: writer, producer", and the copyright reads
"Copyright 2019, Audible Mount Diablo - All Rights Reserved." 156 of 209 episode descriptions credit
SMD, usually "Sponsored by Mount Diablo Interpretive Association in partnership with Save Mount
Diablo". 5 are "presented by Save Mount Diablo" (the nine-part "Harvest of Fire" series). The
episodes include trail audio tours, e.g. "The Falls Trail". `/experience/online-presentations/` …

Its `where`: https://rss.libsyn.com/shows/136346/destinations/844139.xml https://savemountdiablo.org
https://savemountdiablo.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("audible_mount_diablo_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
