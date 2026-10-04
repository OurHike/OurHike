"""Mohonk Preserve: suggested hikes, its Suggested Hikes page read here (decision 54 wave 5, section K,
2026-10-04).

- `mohonk_suggested_hikes`: 13 hikes, 8 by trailhead and 5 that continue onto neighbouring lands, each its name, its
  trailhead and its printable PDF map. The page states no single distance for any hike, so none lands. The PDF maps
  (the coverage audit's five, and seven more) are linked from the rows and are drawings, not read.
  mohonkpreserve.org's robots.txt asks `Crawl-delay: 10`.

The reader is extract/_pages_content.py's ContentPages with the `mohonk_suggested_hikes` site parser: the rows
hashed for the change check (no page validator decides FRESH), facts and the link only, never the club's own
wording. Its row in sources.json holds the terms as found, the live read and the measured key, the trailhead and the
hike's name.

The note this replaces read, whole:

Mohonk Preserve: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

Prose and PDF. The routes run on `mohonk_trails` names, so a name-join is plausible (Reasoned). Skeptic
additions: `/visit/trailmaps/` (`modified` 2026-09-23) adds "Maps with suggested hikes at individual
trailheads are also available for download". Guided hikes are not in WordPress at all: …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/visit/activities/suggested-hikes/` (`modified` 2026-09-24):
hikes by trailhead, e.g. "Undercliff-Overcliff Loop (Via East Trapps Connector Trail)" and "Millbrook
Ridge Loops", plus 5 map PDFs (`WT_SuggestedHike_AWOSTING_MAPONLY_6.19.20.pdf`,
`…SKYTOP_MAP_6.14.21.pdf` ×4). `tribe_events` holds 0 events from 2026-10-01 on. `Hub Events (public)`
holds 3 rows (2025-01-13).

Its `where`: https://mohonkpreserve.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("mohonk_suggested_hikes",)
RESOURCES = [content_pages("mohonk_suggested_hikes", crawl_delay=10.0)]
