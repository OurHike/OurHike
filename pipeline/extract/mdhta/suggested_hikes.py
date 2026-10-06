"""Maah Daah Hey Trail Association: suggested hikes, its 19 trail pages read here (decision 54 wave 5,
section K, 2026-10-04).

- `mdhta_trails`: mdhta.com/trails/ (two archive pages) and its 19 trail pages, each its name and, on 12, its
  distance. The Campgrounds entries are points of interest and the Overview and 'Ideal for' entries prose; none is
  read.

The reader is extract/_pages_content.py's ContentPages with the `mdhta_trails` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row in
sources.json holds the terms as found, the live read and the measured key, `link`.
"""

from extract._pages_content import content_pages

CLAIMS = ("mdhta_trails",)
RESOURCES = [content_pages("mdhta_trails")]
