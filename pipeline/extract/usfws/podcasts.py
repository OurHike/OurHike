"""US Fish & Wildlife Service: podcasts, 1 feed read here (decision 54 wave 3, section C, 2026-10-04).

- `usfws_future_of_conservation_podcast`: Future of Conservation, the National Conservation Training
  Center's show: 13 episodes, 2025-01-06 to 2026-08-06, at the feed URL Apple's lookup gives for
  show id1789144144, which www.fws.gov/page/future-conservation-podcast-series links. Nature's
  Infrastructure and the NCTC collection page link no feed URL, and none was looked up.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

US Fish & Wildlife Service: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

National conservation programming, not trail audio. Low value to a hiker.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): fws.gov podcast pages: "The Future of Conservation" (2026
series), Nature's Infrastructure, NCTC podcasts. Skeptic adds the exact URLs (HTTP 200 on
2026-10-01): `https://www.fws.gov/page/future-conservation-podcast-series` (page; episodes link to
Apple Podcasts show `id1789144144`) and `https://www.fws.gov/library/collections/podcasts-national-
conservation-training-center`. Neither page links an RSS URL. The feed behind the Apple show was not
looked up.

Its `where`: https://www.fws.gov/page/future-conservation-podcast-series
https://www.fws.gov/library/collections/podcasts-national-conservation-training-center
https://fws.gov

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("usfws_future_of_conservation_podcast",)
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
