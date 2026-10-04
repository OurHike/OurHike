"""Maah Daah Hey Trail Association: suggested hikes, its 19 trail pages read here (decision 54 wave 5,
section K, 2026-10-04).

- `mdhta_trails`: mdhta.com/trails/ (two archive pages) and its 19 trail pages, each its name and, on 12, its
  distance. The Campgrounds entries are points of interest and the Overview and 'Ideal for' entries prose; none is
  read.

The reader is extract/_pages_content.py's ContentPages with the `mdhta_trails` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row in
sources.json holds the terms as found, the live read and the measured key, `link`.

The note this replaces read, whole:

Maah Daah Hey Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 19 trail pages (`/trails/`, with distance, campgrounds, overview
and "Ideal for").

Its `where`: https://mdhta.com/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("mdhta_trails",)
RESOURCES = [content_pages("mdhta_trails")]
