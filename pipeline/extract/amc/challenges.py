"""Appalachian Mountain Club: challenges, the Four Thousand Footer Club's lists read here (decision 54 wave
5, section K, 2026-10-04).

- `amc_four_thousand_footer_lists`: amc4000footer.org's three list pages, the White Mountain 48, the New England 67
  and the New England Hundred Highest's 33 below 4,000 feet, each peak its rank, state, elevation (and whether the
  club estimated it from contours) and, on the Hundred Highest, whether a trail reaches it.

The reader is extract/_pages_content.py's ContentPages with the `amc_four_thousand_footer_lists` site parser: the
rows hashed for the change check (no page validator decides FRESH), one row a place on the challenge's list, its
facts and the link, never the club's prose and never anyone who finished. Its row in sources.json holds the terms as
found, the live read and the measured key, the list and the peak's rank. The Northeast 111's list and the
applications are PDFs, not read. The NET Hike Challenge (with CFPA) is newenglandtrail.org's, not read here.
"""

from extract._pages_content import content_pages

CLAIMS = ("amc_four_thousand_footer_lists",)
RESOURCES = [content_pages("amc_four_thousand_footer_lists")]
