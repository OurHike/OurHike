"""Colorado Mountain Club: places, refused by the club's terms (decision 54, wave 5). The Routes & Places library
holds campgrounds, huts and trailheads with a coordinate each (the coverage audit, 2026-10-01: 'Address:
-105.710909, 39.51101561' on /education-adventure/trips/routes-places/abyss-lake-trail), and the terms exclude
from their licence 'use of any data mining, robots or similar data gathering or extraction methods', quoted in
`terms`. A refusal is a note, not a puzzle: nothing past the terms page was requested. Held until the club
permits, the maintainer's request to send.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "www.cmc.org/robots.txt (Plone's; its `Disallow: /*?` applies to Googlebot only) and "
        "/legal/terms-conditions, read 2026-10-04 under lib/user_agent.py's agent: the licence and its exclusions "
        "(a) to (g), quoted in `terms`.",
        "the coverage audit (2026-10-01, batch c5_regional_2): the library's faceted query reports 1,354 records, "
        "each with a trailhead coordinate; its skeptic fetched nothing from cmc.org because of §3(e).",
    ),
    where=(
        "https://www.cmc.org/legal/terms-conditions",
        "https://www.cmc.org/",
    ),
    terms=(
        'https://www.cmc.org/legal/terms-conditions (read 2026-10-04): "You are granted a limited, nonexclusive, '
        "non-sublicensable license to access and use the Sites and electronically copy (except where prohibited "
        "without a license) and print hard copy portions of the Site Content for your informational, noncommercial "
        "and personal use. Such license is subject to these Terms and excludes: (a) any resale of the Sites or Site"
        " Content; (b) the collection and use of any product listings, pictures or descriptions; (c) the "
        "distribution, public performance or public display of any Site Content; (d) modifying or otherwise making "
        "any derivative uses of the Sites and the Site Content, or any portion thereof; (e) use of any data mining,"
        " robots or similar data gathering or extraction methods; (f) downloading (other than page caching) of any "
        "portion of the Sites, the Site Content or any information contained therein, except as expressly permitted"
        " on the Sites or pursuant to separate terms; or (g) any use of the Sites or the Site Content other than "
        'for its intended purpose."'
    ),
    reason="refused: the club's terms exclude data mining, robots and similar extraction from their licence (quoted in `terms`)",
)
