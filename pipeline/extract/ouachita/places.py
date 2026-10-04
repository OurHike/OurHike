"""Friends of the Ouachita Trail: places, in the navigation-points PDF only a person can pair up (decision 54,
wave 4, read live 2026-10-04).

The water sources PDF ("OUACHITA TRAIL NAVIGATION POINTS", 2019) marks its access points ("FR #6010. Access
point.") and names the state parks it passes (Talimena, Queen Wilhelmina, Pinnacle Mountain) in its
description column, which pypdf hands over lines away from each row's mile and fix once a description wraps,
so a place could be paired with its fix only by guessing (ouachita/points_of_interest.py says the same of its
water). The state parks are areas another folder's state park layers hold; the access points would be points.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt on www.friendsoftheouachita.org (`Crawl-delay: 10`, honoured), then the PDF whole, read "
        "2026-10-04 under lib/user_agent.py's agent: "
        "https://www.friendsoftheouachita.org/wp-content/uploads/2025/05/OT_Water_Sources_rev_2019-03-01.pdf, "
        '68,501 bytes, ETag "6aab485b-10b95", 7 pages; descriptions wrapping onto later lines, apart from their '
        "rows' miles and fixes.",
        "the coverage audit (2026-10-01, batch c6_regional_3): 46 rows marked 'Access point'; the state parks named.",
    ),
    where=("https://www.friendsoftheouachita.org/wp-content/uploads/2025/05/OT_Water_Sources_rev_2019-03-01.pdf",),
    reason="a PDF only a person can read: each row's description sits apart from its fix in the text layer",
)
