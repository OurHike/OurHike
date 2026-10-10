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
"""

from extract._pages_content import content_pages

CLAIMS = ("patc_tuscarora_sections",)
RESOURCES = [content_pages("patc_tuscarora_sections")]
