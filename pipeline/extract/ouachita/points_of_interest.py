"""Friends of the Ouachita Trail's shelter list: 23 Ouachita Trail shelters, each with its mile marker, and a
fix for the 12 from Rock Garden (MM 9.4) to Story Creek (MM 116.7).

Decision 54, wave 5: read live on 2026-10-04 (robots.txt first, `Crawl-delay: 10` honoured,
lib/user_agent.py's agent) through WordPress page 326's REST route, and registered in sources.json, where the
row carries the count, the measured key and what holds it back.

- `foot_trail_shelters`: 23 shelters, keyed on the name; 11 land with no geometry, because the page gives
  them a mile marker and no fix, and a coordinate is never looked up from a name.

The loaded USFS recreation sites hold no shelter under Ouachita NF (the coverage audit's skeptic,
2026-10-01), so this list is the only one of the trail's shelters.

NOT LANDED, read the same day: the water sources PDF the club links,
https://www.friendsoftheouachita.org/wp-content/uploads/2025/05/OT_Water_Sources_rev_2019-03-01.pdf (68,501
bytes, ETag "6aab485b-10b95", 7 pages, created 2019-03-01, "Most fixes use NAD27 datum. Not all verified.").
pypdf's plain extraction hands each row's mile, section and fix over on one line and its description, the
only place a row says whether there is water ("Reliable water source", "Rainy season water source", "No
water"), lines later and out of order once a description wraps, so a parser could pair a source with its
description only by guessing. A PDF only a person can read, for now; its compiler is named on every page,
which nothing here would copy.
"""

from datetime import date

from extract._contract import SameAs
from extract._pages_points import page_points

CLAIMS = ("foot_trail_shelters",)
RESOURCES = [page_points(key) for key in CLAIMS]

SAME_AS = (
    SameAs(
        original="foot_trail_shelters",
        copy=("https://www.friendsoftheouachita.org/wp-content/uploads/2025/05/Ouachita-Trail-Shelters-5-7-25.pdf",),
        confirmed=date(2026, 10, 4),
        checked=(
            "The Shelter Guide PDF the shelters page links ('To download Shelter Guide click HERE'), read "
            '2026-10-04: 216,300 bytes, ETag "6aa5099a-34cec", 2 pages, made 2025-05-07 in Word. Its text lists '
            "the same 23 shelters in the same order with the same 12 fixes and 23 mile markers as page 326's "
            "list (modified 2025-11-11), line for line. The page is the one extracted, as the newer and the one "
            "fixture mode can read.",
        ),
    ),
)
