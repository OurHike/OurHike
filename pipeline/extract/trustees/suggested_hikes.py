"""The Trustees of Reservations: suggested hikes, its Hikers Top Ten read here (decision 54 wave 5, section K,
2026-10-04).

- `trustees_hikers_top_ten`: thetrustees.org/program/the-trustee-hikers-top-ten/, ten properties the Hike Trustees
  group voted its favourites, each its rank, town and page. The members' quotes are not read.

The reader is extract/_pages_content.py's ContentPages with the `trustees_hikers_top_ten` site parser: the rows
hashed for the change check (no page validator decides FRESH), facts and the link only, never the club's own
wording. Its row in sources.json holds the terms as found, the live read and the measured key, `name`. The place
pages' 'Ideas for Your Visit' are prose and not read; the Hike Trustees challenge is the challenges cell's.

The note this replaces read, whole:

The Trustees of Reservations: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/program/the-trustee-hikers-top-ten/` and "Ideas for Your Visit"
on place pages.

Its `where`: https://thetrustees.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("trustees_hikers_top_ten",)
RESOURCES = [content_pages("trustees_hikers_top_ten")]
