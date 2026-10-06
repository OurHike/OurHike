"""Mount Rogers Appalachian Trail Club: suggested hikes, its Suggested Hikes page read here (decision 54
wave 5, section K, 2026-10-04).

- `mratc_suggested_hikes`: mratc.org/suggested-hikes, 7 hikes under three of its seven kinds, each its name, miles,
  shape and difficulty from the line under it ('8 miles | One way | Moderate'). The turn-by-turn paragraphs, and the
  coordinates written in them without a sign, are not read.

The reader is extract/_pages_content.py's ContentPages with the `mratc_suggested_hikes` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its
row in sources.json holds the terms as found, the live read and the measured key, the kind of hike and its name.

The note this replaces read, whole:

Mount Rogers Appalachian Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

Whether those four sections load by script is UNKNOWN (no browser was used).

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://www.mratc.org/suggested-hikes` (page): 7 hikes render (2
A.T., 3 A.T.-linked, 2 Iron Mountain). Each has distance, one-way or loop, difficulty and turn-by-turn
prose, with 15 coordinate pairs in the text. Four more headings (High Points, Damascus, Grayson
Highlands, Backpacking) render no hikes. 63 scheduled events are in `event-pages-sitemap.xml`.

Its `where`: https://www.mratc.org/suggested-hikes

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("mratc_suggested_hikes",)
RESOURCES = [content_pages("mratc_suggested_hikes")]
