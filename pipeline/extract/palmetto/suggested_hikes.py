"""Palmetto Conservation Foundation: suggested hikes, the Palmetto Trail's 33 passage pages read here
(decision 54 wave 5, section K, 2026-10-04).

- `palmetto_passages`: palmettotrail.org's sitemap.xml and the 33 /trails/trail/ pages it lists, each its length,
  difficulty, region and the first-line answers its fact grid gives: surface, pets, fees, camping and whether the
  trail crosses hunting grounds (Yes, No, Depends). The explanations under those answers, the description and the
  trailheads' coordinates are not read.

The reader is extract/_pages_content.py's ContentPages with the `palmetto_passages` site parser: the rows hashed for
the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row
in sources.json holds the terms as found, the live read and the measured key, `link`.

The note this replaces read, whole:

Palmetto Conservation Foundation: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 33 passage pages: length, difficulty, activities and description.

Its `where`: https://palmettoconservation.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("palmetto_passages",)
RESOURCES = [content_pages("palmetto_passages")]
