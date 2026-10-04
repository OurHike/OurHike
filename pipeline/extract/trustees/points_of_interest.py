"""The Trustees of Reservations: points of interest, published as Google Maps directions links, and not landed
(decision 54, wave 5, read live 2026-10-04).

Each of the 132 place pages (places-sitemap.xml) gives its parking as a "Get directions" link to Google Maps
(Notchview's: `/maps/dir//Notchview+%7C+The+Trustees+of+Reservations,+83+Old+Rte+9,+Windsor,+MA+01270/
@42.5028833,-73.0324264,465m/...`). The `@` pair is the map view the link was made from and the destination is
Google's place for an address, so neither is a fix the Trustees publish, and a point is never taken from a
geocode. The places' "Facilities & Accessibility" sections are prose. Needs a per-site reader, not built in this
pull request, and a parking fix a person reviews. The Trustees' own GIS (`TTOR_2`, the coverage audit) holds no
trailhead or parking layer.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (Yoast's, `Disallow:` empty, no Crawl-delay), then sitemap_index.xml, places-sitemap.xml (132 "
        "`/place/` pages) and /place/notchview/, read 2026-10-04 under lib/user_agent.py's agent: the page's only "
        "coordinate is inside its Google Maps directions link; the WordPress REST types expose no place type.",
        "the coverage audit (2026-10-01, batch c4_regional_1): page only, 132 pages; `/places-to-go/inns-campgrounds/`.",
    ),
    where=("https://thetrustees.org/places-sitemap.xml", "https://thetrustees.org/place/notchview/"),
    reason="published as Google Maps links: the coordinates are Google's view and place, not the Trustees' fix",
)
