"""Keystone Trails Association: suggested hikes, Favorite Hikes in Pennsylvania read here (decision 54 wave 5,
section K, 2026-10-04).

- `kta_favorite_hikes`: kta-hike.org's favourite hikes, 32 in seven groups, each its name, county and the URL of the
  page that describes it (another organisation's, linked and never fetched); the English and Spanish descriptions
  are not read.

The reader is extract/_pages_content.py's ContentPages with the `kta_favorite_hikes` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its
row in sources.json holds the terms as found, the live read and the measured key, the group and the hike's name.

The note this replaces read, whole:

Keystone Trails Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c1_at_clubs_north).

—

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `favorite-hikes-in-pennsylvania.html` (page; bilingual EN/ES, each
hike with county, link and description, e.g. "Kurmes Trail … 2.2-mile loop"). Also
`southcentralaccessible.html` and `accessible-philadelphia.html`.

Its `where`: https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://kta-hike.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("kta_favorite_hikes",)
RESOURCES = [content_pages("kta_favorite_hikes")]
