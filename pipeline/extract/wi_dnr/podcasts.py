"""Wisconsin DNR: podcasts, 2 feeds read here (decision 54 wave 3, section C, 2026-10-04).

- `wdnr_wild_wisconsin_podcast`: Wild Wisconsin, Off the Record, on transistor.fm: 59 episodes,
  2017-09-01 to 2021-06-16.
- `silvicast_podcast`: SilviCast, which the Wisconsin Forestry Center and WDNR produce together, on
  buzzsprout: 71 episodes, 2020-06-12 to 2026-10-01. About forestry practice rather than hiking (the
  coverage audit); loaded all the same (decision 54), and dbt decides what any of it is for.

Each feed's row in sources.json holds its <copyright> line verbatim, its live read of 2026-10-04 and
its measured key, `guid`. The reader is extract/_content.py's PodcastEpisodes: extract/_kinds.py's
PodcastFeed with every tag that names a person left out before dlt sees the row (an item's
itunes:author, which carries the guests' and hosts' names, RSS <author>, dc:creator, podcast:person,
itunes:owner) and the row's own `person_fields`. The lane is the type's, monthly. Episodes are
linked, never re-hosted: an <enclosure> lands as its URL, and the audio is never fetched. A feed is
what its host serves, so an episode's absence is never its removal.

Before decision 54's wave 3, 2026-10-04, this file was a note. It read, whole:

Wisconsin DNR Open Data: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Dormant for five years. Load only if the podcasts mart accepts archives. SilviCast is live, but its
audience is foresters, so it is a weak fit.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "Wild Wisconsin – Off the Record": RSS
`https://feeds.transistor.fm/wild-wisconsin-off-the-record`, 59 episodes, latest release 2021-06-16
(iTunes id 1392683302). Skeptic adds (Measured, Apple Podcasts search "Wisconsin Department of
Natural Resources"): SilviCast, by the Wisconsin Forestry Center and the Wisconsin Department of
Natural Resources: RSS `https://rss.buzzsprout.com/1135730.rss`, 70 episodes, latest 2026-08-03 (id
1518316928). It is active, co-produced, and about forestry practice rather than hiking.

Its `where`: https://feeds.transistor.fm/wild-wisconsin-off-the-record
https://rss.buzzsprout.com/1135730.rss

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._content import podcast_episodes

CLAIMS = ("wdnr_wild_wisconsin_podcast", "silvicast_podcast")
RESOURCES = [podcast_episodes(key) for key in CLAIMS]
