"""Foothills Trail Conservancy: elevation, published only as two pictures of profiles, which are not data.

Two JPEG images of the trail's west and east profiles. No parser in decision
54's waves reads an elevation off a picture, and a figure a person read off
one would be a reading, not a measurement, so they stay a note and 3DEP
(_shared/usgs/) is the profile.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "HEAD 2026-10-03, after robots.txt (Crawl-delay 10, honoured): "
        "`/wp-content/uploads/2024/01/West-Elevation-Profile-Final-1-scaled.jpg`, image/jpeg, 146,238 bytes, and "
        "`East-Elevation-Profile-Final-1-scaled.jpg`, 137,303 bytes, both Last-Modified 2026-04-25",
        "coverage audit (2026-10-01, batch c5_regional_2): these are the club's only elevation products",
    ),
    where=(
        "https://foothillstrail.org/wp-content/uploads/2024/01/West-Elevation-Profile-Final-1-scaled.jpg",
        "https://foothillstrail.org/wp-content/uploads/2024/01/East-Elevation-Profile-Final-1-scaled.jpg",
        "https://foothillstrail.org/",
    ),
    reason="pictures of profiles, not data: no reader can take an elevation from them",
)
