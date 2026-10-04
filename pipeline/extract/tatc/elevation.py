"""Tidewater Appalachian Trail Club: elevation, published as a PDF of spot heights at named places, not landed.

"A.T. Distances and Elevations – from Paul Wolf Shelter to Priest Shelter", revised 2009-02-20 by a named
individual (not copied here). Read whole on 2026-10-04 (decision 54's wave 4): page 1 is a 14-landmark
distance matrix, page 2 ten spot elevations as text ("Reeds Gap 2,645 - ft", "Tye River 997 - ft"), each at a
named place and none with a coordinate or an A.T. mile. int_elevation__club_samples holds an elevation at a
point, and placing one of these would mean finding the place by its name, which this pipeline never does. So
they stay a note, at most a cross-check on 3DEP (_shared/usgs/) that a person could make.

A HIKER'S SAFETY, in the sheet's own words, which lands nowhere: "Gid Spring is very seasonal. When dry, which
is most of the time; there is no reliable water on the Appalachian Trail between Maupin Field Shelter and the
Harpers Creek Shelter." Gid Spring is a water point ATC's layers lack, with no coordinate here either, and the
sheet is a 2009 compilation.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "HEAD 2026-10-03, after robots.txt (no Crawl-delay; 2 s kept between requests): "
        "`https://tidewateratc.com/wp-content/uploads/2026/01/AT-Distances-and-Elevation-Info.pdf`, "
        "application/pdf, 74,255 bytes, Last-Modified 2026-01-03",
        "coverage audit (2026-10-01): 10 spot elevations such as Reeds Gap 2,645 ft, Three Ridges 3,970 ft, Tye "
        "River 997 ft and Priest Shelter 4,063 ft; linked from `/tatc-education/`",
        "GET 2026-10-04 under lib/user_agent.py's agent, after robots.txt (no Crawl-delay; 2 s kept): 74,255 bytes, "
        'ETag "1220f-6478239345ed1", 2 pages; pypdf reads the matrix and the ten elevations as text, each beside '
        "a place name and no coordinate or mile",
    ),
    where=(
        "https://tidewateratc.com/wp-content/uploads/2026/01/AT-Distances-and-Elevation-Info.pdf",
        "https://tidewateratc.org/",
    ),
    reason="spot heights at named places with no coordinate: placing one would be geocoding from a name",
)
