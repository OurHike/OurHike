"""Cumberland Valley Appalachian Trail Club: suggested hikes, its fall foliage hikes read here (decision 54
wave 5, section K, 2026-10-04).

- `cvatc_foliage_hikes`: 'Great Fall Foliage Hikes In South Central PA', four hikes, each its name, miles, shape and
  difficulty as its paragraph's first clause states them; the directions after it are not read.

The reader is extract/_pages_content.py's ContentPages with the `cvatc_foliage_hikes` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its
row in sources.json holds the terms as found, the live read and the measured key, `name`.
"""

from extract._pages_content import content_pages

CLAIMS = ("cvatc_foliage_hikes",)
RESOURCES = [content_pages("cvatc_foliage_hikes")]
