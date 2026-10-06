"""The Trustees of Reservations: suggested hikes, its Hikers Top Ten read here (decision 54 wave 5, section K,
2026-10-04).

- `trustees_hikers_top_ten`: thetrustees.org/program/the-trustee-hikers-top-ten/, ten properties the Hike Trustees
  group voted its favourites, each its rank, town and page. The members' quotes are not read.

The reader is extract/_pages_content.py's ContentPages with the `trustees_hikers_top_ten` site parser: the rows
hashed for the change check (no page validator decides FRESH), facts and the link only, never the club's own
wording. Its row in sources.json holds the terms as found, the live read and the measured key, `name`. The place
pages' 'Ideas for Your Visit' are prose and not read; the Hike Trustees challenge is the challenges cell's.
"""

from extract._pages_content import content_pages

CLAIMS = ("trustees_hikers_top_ten",)
RESOURCES = [content_pages("trustees_hikers_top_ten")]
