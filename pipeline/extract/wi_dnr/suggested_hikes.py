"""Wisconsin DNR: suggested hikes, its properties' hiking pages read here (decision 54 wave 5, section K,
2026-10-04).

- `wi_dnr_hiking`: the sitemap's 46 property hiking pages, found through its ten sitemap pages; the 20 that state
  each trail's length in its heading land 170 trails, each its name, property, length, shape and difficulty. The
  other 26 give the length in the department's paragraph, which is not read, and land none.

The reader is extract/_pages_content.py's ContentPages with the `wi_dnr_hiking` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row in
sources.json holds the terms as found, the live read and the measured key, the property's hiking page and the
trail's name.
"""

from extract._pages_content import content_pages

CLAIMS = ("wi_dnr_hiking",)
RESOURCES = [content_pages("wi_dnr_hiking")]
