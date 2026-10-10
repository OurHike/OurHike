"""Mount Rogers Appalachian Trail Club: suggested hikes, its Suggested Hikes page read here (decision 54
wave 5, section K, 2026-10-04).

- `mratc_suggested_hikes`: mratc.org/suggested-hikes, 7 hikes under three of its seven kinds, each its name, miles,
  shape and difficulty from the line under it ('8 miles | One way | Moderate'). The turn-by-turn paragraphs, and the
  coordinates written in them without a sign, are not read.

The reader is extract/_pages_content.py's ContentPages with the `mratc_suggested_hikes` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its
row in sources.json holds the terms as found, the live read and the measured key, the kind of hike and its name.
"""

from extract._pages_content import content_pages

CLAIMS = ("mratc_suggested_hikes",)
RESOURCES = [content_pages("mratc_suggested_hikes")]
