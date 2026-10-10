"""PA DCNR (PASDA's folder): challenges, the DCNR GeoTrail's caches read here (decision 54 wave 5, section K,
2026-10-04).

- `dcnr_geotrail`: pa.gov's DCNR GeoTrail page for America's 250th, 25 state parks and environmental education
  centers, each its cache's theme, whether it is marked accessible, and its link on geocaching.com. The caches'
  coordinates are geocaching.com's, under its terms, and are not read.

The reader is extract/_pages_content.py's ContentPages with the `dcnr_geotrail` site parser: the rows hashed for the
change check (no page validator decides FRESH), one row a place on the challenge's list, its facts and the link,
never the club's prose and never anyone who finished. Its row in sources.json holds the terms as found, the live
read and the measured key, `name`. The steward is PA DCNR (org:padcnr), whose row this is; the cell sat in pasda/ in
the coverage audit.
"""

from extract._pages_content import content_pages

CLAIMS = ("dcnr_geotrail",)
RESOURCES = [content_pages("dcnr_geotrail")]
