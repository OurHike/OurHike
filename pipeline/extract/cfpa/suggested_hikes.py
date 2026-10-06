"""Connecticut Forest & Park Association: suggested hikes, its Find a Trail list read here (decision 54
wave 5, section K, 2026-10-04).

- `cfpa_trails`: ctwoodlands.org/trails/, the Blue-Blazed Hiking Trail System's 57 trails, each its name, mileage
  and page, from the index alone; ctwoodlands.org's robots.txt asks `Crawl-delay: 10`, so one request a month.

The reader is extract/_pages_content.py's ContentPages with the `cfpa_trails` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row in
sources.json holds the terms as found, the live read and the measured key, `name`.
"""

from extract._pages_content import content_pages

CLAIMS = ("cfpa_trails",)
RESOURCES = [content_pages("cfpa_trails", crawl_delay=10.0)]
