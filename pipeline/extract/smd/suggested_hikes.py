"""Save Mount Diablo: suggested hikes, its field guide 'Hikes in the Diablo Range' read here (decision 54
wave 5, section K, 2026-10-04).

- `smd_diablo_range_hikes`: the field guide's 47 numbered hikes, each its name, its region and the part of it, and
  the post it links; the posts are Save Mount Diablo's writing and are not fetched. savemountdiablo.org's robots.txt
  asks `Crawl-delay: 3`.

The reader is extract/_pages_content.py's ContentPages with the `smd_diablo_range_hikes` site parser: the rows
hashed for the change check (no page validator decides FRESH), facts and the link only, never the club's own
wording. Its row in sources.json holds the terms as found, the live read and the measured key, the region's part and
the hike's name.

The note this replaces read, whole:

Save Mount Diablo: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Terms-blocked.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/experience/field-guides/hikes-in-the-diablo-range/` lists 47
numbered hikes by region, each linking a blog post, e.g.
`/blog/mount-diablo-state-park-five-peaks-hike/`. The "Northern Diablo Range Hiking Guide" PDF is behind
an email form.

Its `where`: https://savemountdiablo.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("smd_diablo_range_hikes",)
RESOURCES = [content_pages("smd_diablo_range_hikes", crawl_delay=3.0)]
