"""Cumberland Valley Appalachian Trail Club: suggested hikes, its fall foliage hikes read here (decision 54
wave 5, section K, 2026-10-04).

- `cvatc_foliage_hikes`: 'Great Fall Foliage Hikes In South Central PA', four hikes, each its name, miles, shape and
  difficulty as its paragraph's first clause states them; the directions after it are not read.

The reader is extract/_pages_content.py's ContentPages with the `cvatc_foliage_hikes` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its
row in sources.json holds the terms as found, the live read and the measured key, `name`.

The note this replaces read, whole:

Cumberland Valley Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/some-great-fall-foliage-hikes-in-south-central-pa.html` (page):
4 hikes (Pole Steeple 6 mi, Flat Rock 5 mi, Cumberland Valley Overlook 6 mi, Perry County Overlook 7 mi)
with turn-by-turn prose

Its `where`: https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://cvatclub.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("cvatc_foliage_hikes",)
RESOURCES = [content_pages("cvatc_foliage_hikes")]
