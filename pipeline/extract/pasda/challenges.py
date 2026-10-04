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

The note this replaces read, whole:

PASDA / PA DCNR: challenges, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

This is a DCNR-run end-to-end programme with a reward, the #1780 shape. Caveat: the cache coordinates
live on geocaching.com, whose terms govern them (not read), so the extractable content is the 25 park
names, themes, hike lengths and GC codes. The park centroids come from DCNR's own …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "DCNR GeoTrail: Celebrating America's 250th",
`https://www.pa.gov/agencies/dcnr/recreation/what-to-do/geocaching/dcnr-geo-trail` (200, read
2026-10-01). It is run with America250PA. 25 geocaches, one per location: state parks and environmental
education centres, for example Beltzville, Benjamin Rush, Black Moshannon, Jennings EEC and White Clay
Creek Preserve. Each location gives a theme, the hike length and terrain (for example "1-mile round trip
over uneven terrain"), and a geocaching.com GC code, from `GCBJH8G` onward. There are 25 distinct codes
on the page. "If you complete all …

Its `where`: https://www.pa.gov/agencies/dcnr/recreation/what-to-do/geocaching/dcnr-geo-trail
https://geocaching.com https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR/MapServer/8
https://pasda.psu.edu/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("dcnr_geotrail",)
RESOURCES = [content_pages("dcnr_geotrail")]
