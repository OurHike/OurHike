"""Oregon Natural Desert Association: suggested hikes, its 24 hike pages read here (decision 54 wave 5,
section K, 2026-10-04).

- `onda_hikes`: hike-sitemap.xml and the 24 /hike/ pages it lists, each its distance, difficulty (1 to 5), best
  times, closest town and drive time from the page's fact list. onda.org's robots.txt asks `Crawl-delay: 10`, so 25
  requests a month. The posts '21 Day Hikes' and the loop hikes are prose and not read.

The reader is extract/_pages_content.py's ContentPages with the `onda_hikes` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row in
sources.json holds the terms as found, the live read and the measured key, `link`. ONDA is one of the four `refuse`
organizations: its Oregon Desert Trail GPX, maps and Databook sit behind a waiver and are not read, and nothing of
this row publishes until its permission is recorded.
"""

from extract._pages_content import content_pages

CLAIMS = ("onda_hikes",)
RESOURCES = [content_pages("onda_hikes", crawl_delay=10.0)]
