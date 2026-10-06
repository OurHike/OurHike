"""Florida Trail Association: suggested hikes, its Day & Section Hike page read here (decision 54 wave 5,
section K, 2026-10-04).

- `fta_day_hikes`: floridatrail.org/day-hike/, the Grab-and-Go and Other Trail Hikes maps, 46 hikes, each its name,
  place where the tooltip gives one, distance (a number only where one figure is stated) and the grab-and-go PDF
  where one is linked. The 16 grab-and-go PDFs the coverage audit names are linked from the rows and not read: the
  page states what this type carries, and the PDFs' trailhead coordinates and camping are points of interest.

The reader is extract/_pages_content.py's ContentPages with the `fta_day_hikes` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row in
sources.json holds the terms as found, the live read and the measured key, the map and the hike's name.
"""

from extract._pages_content import content_pages

CLAIMS = ("fta_day_hikes",)
RESOURCES = [content_pages("fta_day_hikes")]
