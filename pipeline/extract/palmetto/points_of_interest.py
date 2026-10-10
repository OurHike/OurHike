"""The Palmetto Trail's map markers and passage lines, from the 33 passage pages, each read for the
`addMarker` and `addSegment` calls its own map script makes.

Decision 54, wave 5: read live on 2026-10-04 (robots.txt first, lib/user_agent.py's agent, 2 s or more
between requests) and registered in sources.json, where the row carries the count, the measured key and what
holds it back.

- `palmetto_trail_passages`: 396 rows, 363 typed markers (parking, trailheads, camping, restrooms, water
  launches and more) and 33 passage lines, keyed on the page and the geometry; the pages are the ones the
  site's sitemap lists under /trails/trail/.

A WATER LAUNCH IS A BOAT LAUNCH, never drinking water, and no marker on any page is typed as water.
not_available.toml [palmetto.trail_lines] SHARES this resource for its lines, and not_available.toml [palmetto.places] says why the passages'
trailheads are points rather than places.

Every row also carries its page's facts, the fact grid's first-line answers and the length, read in the same fetch
(the lead's ruling of 2026-10-04: one reader of the 33 passage pages), for not_available.toml [palmetto.suggested_hikes], which SHARES
this resource too. Their columns are extract/_pages_points.py's PALMETTO_FACT_COLUMNS. They change no marker row's
shape or key.
"""

from extract._pages_points import page_points

CLAIMS = ("palmetto_trail_passages",)
RESOURCES = [page_points(key) for key in CLAIMS]
