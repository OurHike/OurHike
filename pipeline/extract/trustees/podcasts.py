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

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

The Trustees of Reservations: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

Coastal-programme content, not trail content, and two episodes, so `_shared/podcasts` material at
most. Licence unstated.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Trustees On The Coast", artist "The Trustees". Apple id
1485305394. RSS `https://anchor.fm/s/102fa3a7c/podcast/rss`: 2 items with enclosures, both dated
2025-03-27 ("A shorebird story: Piping Plovers on Trustees beaches", "Raise the Road! Protecting
Argilla Road Access to Crane Beach"), with an empty `<copyright>`. Linked from
`www.onthecoast.thetrustees.org/podcast`, which this sandbox's proxy refused (502), so it was not
read. Separately, `/content/audio-tours/` offers deCordova sculpture audio tours through the OnCell
app. Those are not trail content.

Its `where`: https://anchor.fm/s/102fa3a7c/podcast/rss
https://www.onthecoast.thetrustees.org/podcast https://thetrustees.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("trustees_on_the_coast_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
