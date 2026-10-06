"""Continental Divide Trail Coalition: suggested hikes, its `hike_suggestion` post type read here with its terms
(decision 54 wave 5, section K, 2026-10-04).

- `cdtc_hike_suggestions`: the page the coverage audit found, cdtcoalition.org/explore-the-trail/day-section-hiking/,
  lists the coalition's `hike_suggestion` custom post type, which its WordPress REST API serves whole: X-WP-Total
  60, one page, read 2026-10-04. Its one taxonomy, `hike_suggestion_category` (the state, and "All Family
  Friendly"), lands as `raw_cdtc__cdtc_hike_suggestions_terms` on the same monthly lane. cdtcoalition.org's
  robots.txt asks `Crawl-delay: 10`, honoured on every request.

The reader is extract/_kinds.py's WordpressPosts and extract/_content.py's SiteTerms, as section C read GMC's hikes:
X-WP-Total is the count and the proof, and the change check a hash of the (id, modified) set. The post bodies carry
ranger-district telephone numbers on 22 of the 60 (2026-10-04), so the row lists `content` and `excerpt` as
person fields and neither loads (decision 59): what lands is each hike's title, link, dates and state, and a
hike's distance, which only its prose states and inconsistently ('nearly 14 miles of trail', 'turn around after
2-3 miles'), is a gap rather than a guess.
"""

from extract._content import site_terms
from extract._kinds import wordpress_posts

CLAIMS = ("cdtc_hike_suggestions",)
RESOURCES = [
    wordpress_posts("cdtc_hike_suggestions", post_type="hike_suggestion", crawl_delay=10.0),
    site_terms("cdtc_hike_suggestions", ("hike_suggestion_category",), crawl_delay=10.0),
]
