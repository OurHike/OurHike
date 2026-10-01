"""The podcast episodes OurHike has tagged to places: reference/podcast_episodes.json, reviewed in git, one row each.

71 episodes, keyed by `spotify_id` (ELT.md, "One key per table"). Places are
tagged on the Podcast desk, a private claude.ai artifact out of CI's reach
(features/PODCAST_PLACES.md), and reviewed into this file; the file is what
loads. A show a club publishes is that club's (atc/podcasts.py extracts The
Green Tunnel's feed); this file is OurHike's own selection across shows.

Each row lands verbatim, as the JSON the reviewer wrote, because the gate dbt
runs over it (int_podcasts__checked, lib/podcasts.py's rules) refuses a row
for its field names and value types, and typed columns would have let dlt
coerce exactly those typos away (ReviewedFile's `verbatim` has the
measurement).
"""

from extract._kinds import reviewed_file

TYPE = "podcasts"
CLAIMS = ("reference/podcast_episodes.json",)
RESOURCES = [reviewed_file("reference/podcast_episodes.json", rows_key="episodes", verbatim=True)]
