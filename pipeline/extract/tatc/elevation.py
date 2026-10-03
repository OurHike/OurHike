"""Tidewater Appalachian Trail Club: elevation, published as a PDF of spot heights, not landed.

"A.T. Distances and Elevations – from Paul Wolf Shelter to Priest Shelter",
revised 2009-02-20 by a named individual (not copied here): a 14-landmark
distance matrix and 10 spot elevations as text, which a wave-4 parser could
read (coverage audit 2026-10-01, batch c2_at_clubs_mid). They are 2009 figures
with no coordinates, so at most a cross-check on 3DEP (_shared/usgs/) at
named places. The matrix also names Gid Spring, a water point ATC's layers
lack, with no coordinates.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "HEAD 2026-10-03, after robots.txt (no Crawl-delay; 2 s kept between requests): "
        "`https://tidewateratc.com/wp-content/uploads/2026/01/AT-Distances-and-Elevation-Info.pdf`, "
        "application/pdf, 74,255 bytes, Last-Modified 2026-01-03",
        "coverage audit (2026-10-01): 10 spot elevations such as Reeds Gap 2,645 ft, Three Ridges 3,970 ft, Tye "
        "River 997 ft and Priest Shelter 4,063 ft; linked from `/tatc-education/`",
    ),
    where=(
        "https://tidewateratc.com/wp-content/uploads/2026/01/AT-Distances-and-Elevation-Info.pdf",
        "https://tidewateratc.org/",
    ),
    reason="a PDF, not landed: decision 54's wave 4 needs a parser for the document",
)
