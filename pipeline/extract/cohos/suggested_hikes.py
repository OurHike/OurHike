"""Cohos Trail Association: suggested hikes, the day-hike page's table read here (decision 54 wave 5, section
K, 2026-10-04).

- `cohos_day_hikes`: cohostrail.org/day-hike/'s table of further suggestions, 22 rows, each its trail or
  destination, where it is, its rank (Easy to Strenuous) and its feature. The twelve favourites above it are
  paragraphs of the association's prose and are not read; the through-hike page is not read.

The reader is extract/_pages_content.py's ContentPages with the `cohos_day_hikes` site parser: the rows hashed for
the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row
in sources.json holds the terms as found, the live read and the measured key, the trail and where it is.

The note this replaces read, whole:

The Cohos Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

A page. Digital databooks are sold.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/day-hike/` (Mt. Crawford, Owls Head, …) and `/through-hike/`.

Its `where`: https://cohostrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("cohos_day_hikes",)
RESOURCES = [content_pages("cohos_day_hikes")]
