"""Standing Stone Trail Club: challenges, the Sweet Sixteen Trail Challenge's points read here (decision 54
wave 5, section K, 2026-10-04).

- `sstc_sweet_16`: /sweet-16-trail-challenge, the 16 points of interest a hiker visits, each its name. The printable
  form's question for each point and the brochure are not read.

The reader is extract/_pages_content.py's ContentPages with the `sstc_sweet_16` site parser: the rows hashed for the
change check (no page validator decides FRESH), one row a place on the challenge's list, its facts and the link,
never the club's prose and never anyone who finished. Its row in sources.json holds the terms as found, the live
read and the measured key, `name`. The End 2 End Challenge is a completion award, and /end-to-end-honorees is its
roster, never read.
"""

from extract._pages_content import content_pages

CLAIMS = ("sstc_sweet_16",)
RESOURCES = [content_pages("sstc_sweet_16")]
