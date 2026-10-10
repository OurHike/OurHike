"""The Green Tunnel, which ATC sponsors: its RSS feed, one row per episode.

The maintainer, reviewing the pull request for #1793 — Rebuild the data
platform as dlt → dbt: seven contracted marts, a monthly refresh, published
docs, and lighter phone downloads, on 2026-10-01: "The green tunnel is
officially sponsored by the atc. Get that." The show's own feed, page and
About page, and George Mason University's announcement of it, name only the
Roy Rosenzweig Center for History and New Media as its producer, and say
nothing of a sponsor (read 2026-10-01). So the sponsorship rests on the
maintainer's statement, which sources.json's `sponsor_note` records beside the
row. The coverage audit had read the show as not ATC's.

The feed lists all 51 episodes. reference/podcast_episodes.json already picks
48 of them for places on the A.T., and stays the editorial file that decides
which episode a hike offers (_shared/podcasts/); this resource lands the
show's own list beside it. The registry row reads `reaches_hikers: false` and
`licence_basis: unresolved` until the maintainer decides what of the feed may
show, because the feed's copyright line is RRCHNM's and grants nothing.
"""

from extract._kinds import podcast_feed

CLAIMS = ("green_tunnel_podcast",)
RESOURCES = [podcast_feed(key) for key in CLAIMS]
