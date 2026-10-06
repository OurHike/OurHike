"""Friends of the Blue Hills: suggested hikes, its Suggested Hikes page read here (decision 54 wave 5,
section K, 2026-10-04).

- `blue_hills_hikes`: friendsofthebluehills.org/hiking-near-boston/, 18 hikes, each its name and its page. No hike
  states a distance as a fact (the 4½-mile St. Moritz loop the coverage audit quotes is a sentence of prose), so
  none lands.

The reader is extract/_pages_content.py's ContentPages with the `blue_hills_hikes` site parser: the rows hashed for
the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row
in sources.json holds the terms as found, the live read and the measured key, `name`.
"""

from extract._pages_content import content_pages

CLAIMS = ("blue_hills_hikes",)
RESOURCES = [content_pages("blue_hills_hikes")]
