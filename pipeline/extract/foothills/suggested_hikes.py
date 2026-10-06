"""Foothills Trail Conservancy: suggested hikes, its section-by-section pages read here (decision 54 wave 5,
section K, 2026-10-04).

- `foothills_sections`: the section-by-section index and its 19 /portfolio/ pages, 13 sections and 6 spurs, each its
  distance, difficulty (per direction where the page gives two), blazes and the trailheads at its ends.
  foothillstrail.org's robots.txt asks `Crawl-delay: 10` and disallows every URL with a query string, so 20 requests
  a month, none with a query.

The reader is extract/_pages_content.py's ContentPages with the `foothills_sections` site parser: the rows hashed
for the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its
row in sources.json holds the terms as found, the live read and the measured key, `link`.

The note this replaces read, whole:

Foothills Trail Conservancy: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

These are a WordPress custom post type (`us_portfolio`). REST could not be checked because `/wp-json/`
returned 503. (Skeptic: re-counted 2026-10-01, still 19 `/portfolio/` links. The 503 is a
human-verification wall, not an outage; see the fetch flags.)

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/section-by-section-2/` links 19 pages under `/portfolio/…`: 13
sections from A1 to A14 and 6 spurs. Each gives distance, difficulty, trailheads and features. Example:
`/portfolio/a1/` is 9.7 mi, "strenuous (ascends 2,000 feet in three miles)".

Its `where`: https://foothillstrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("foothills_sections",)
RESOURCES = [content_pages("foothills_sections", crawl_delay=10.0)]
