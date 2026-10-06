"""Potomac Appalachian Trail Club: suggested hikes, the Tuscarora Trail's section guides read here (decision
54 wave 5, section K, 2026-10-04).

- `patc_tuscarora_sections`: hikethetuscarora.org's seven pages of sections, 22 sections of the 250-mile trail,
  each its span, miles, PATC map and maximum and minimum elevation. The parking and shelter coordinates the pages
  state sit in PATC's own sentences and are not read here.

The reader is extract/_pages_content.py's ContentPages with the `patc_tuscarora_sections` site parser: the rows
hashed for the change check (no page validator decides FRESH), facts and the link only, never the club's own
wording. Its row in sources.json holds the terms as found, the live read and the measured key, `section`.

Not read: `Hikes_Sort/0`, 40 hike footprints whose Link field points at the paid Avenza maps (an ArcGIS layer, for
the lead's wave 1 list), and PATC's guidebooks, which are sold. The home page's closure of the Doll Ridge section
(lost landowner permission) is decision 53's: patc_tuscarora_updates reads /updates.

The note this replaces read, whole:

Potomac Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

The Avenza hikes fall under the Council term and point at paid maps, the same issue as the `avenza`
refuse row. The section guides are the club's own free prose.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `Hikes_Sort/0`: 40 hike footprints (Name, Length_mi, ElevGn_ft,
Difficulty, Link → `link.avenza.com`, the paid maps), 2021-09-24. hikethetuscarora.org: 22 section
guides (distance, PATC map, elevations, access coordinates, camping). The guidebooks (Circuit Hikes 11th
ed., Hikes in the Washington Region Part B 6th ed. 2025, A.T. guides) are sold and not loadable

Its `where`: https://link.avenza.com https://hikethetuscarora.org

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("patc_tuscarora_sections",)
RESOURCES = [content_pages("patc_tuscarora_sections")]
