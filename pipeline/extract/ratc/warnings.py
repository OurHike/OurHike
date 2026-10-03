"""Roanoke Appalachian Trail Club: warnings, held for the same reason as closures.py: www.ratc.org's robots.txt
answered 502 to our agent on both reads of 2026-10-03.

The club's warnings are regulations and a water hazard on its McAfee Knob and Triple Crown page
(WordPress page 2821, modified 2026-02-24: camping only in 7 designated areas, fire rings, group sizes,
"There are no natural water sources along the A.T. in the Dragons Tooth area, so bring all your water"),
and the mixed RATC News posts (category 13). Under decision 7 they are warnings. Nothing is fetched until
a robots.txt read answers 200 (RFC 9309 reads a 5xx as disallow); closures.py says what settles it.
ATC's resources carry the bear and high-water rows on the section meanwhile.

Before this, the file was the coverage audit's note (confirmed 2026-10-01, batch c3_at_clubs_south),
whose `checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "https://www.ratc.org/robots.txt, read under our agent at 2026-10-03 22:06 and 22:15 UTC (decision 53 "
        "phase B): HTTP 502, empty body, both times. Read as disallow (RFC 9309); nothing else was asked.",
        "(decision 53 inventory, batch 2, earlier on 2026-10-03) /wp-json/wp/v2/pages?slug=mcafee-knob-and-the-"
        "triple-crown: page 2821, modified 2026-02-24T21:18:48; it links facebook.com/RoanokeATC for 'latest "
        "news and alerts'.",
        "(coverage audit, 2026-10-01) `https://www.ratc.org/at-hiking/mcafee-knob-and-the-triple-crown/` (page, "
        'modified 2026-02-24). Standing federal rules for VA 624–US 220: "NO camping outside of 7 designated '
        'areas", no fires outside metal rings, group size 25 for day hikes and 10 overnight. Water: "There are '
        'no natural water sources along the A.T. in the Dragons Tooth area, so bring all your water". The Dragons '
        "Tooth Special Biological Area is closed to camping. A drone prohibition. The bears category (id 31) has "
        "2 posts, both 2016.",
    ),
    where=(
        "https://www.ratc.org/robots.txt",
        "https://www.ratc.org/at-hiking/mcafee-knob-and-the-triple-crown/",
        "https://www.ratc.org/wp-json/wp/v2/posts?categories=13",
    ),
    reason=(
        "held: the host's robots.txt answered 502 on both of this session's reads, which RFC 9309 reads as "
        "disallow; register the inventory's drafted rows after a 200 read"
    ),
)
