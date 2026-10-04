"""Foothills Trail Conservancy: places, published as lists with no coordinate, and not landed (decision 54, wave
5, read 2026-10-04). The nearby state parks page names seven SC state parks and the registration page three
kiosks and their parking fees ($5/day Oconee, $6/day Table Rock, $2/day USFS Whitewater Falls, the coverage
audit 2026-10-01), with no fix. The trail's access points are loaded in foothills/points_of_interest.py.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "foothillstrail.org/robots.txt (`Disallow: /*?`, `Crawl-delay: 10`, both honoured), then "
        "/nearby-state-parks/, read 2026-10-04 under lib/user_agent.py's agent: 200, 135,683 bytes, no coordinate "
        "in the page.",
        "the coverage audit (2026-10-01, batch c5_regional_2): /registration/ lists 3 kiosks and the parking fees.",
    ),
    where=(
        "https://foothillstrail.org/nearby-state-parks/",
        "https://foothillstrail.org/registration/",
    ),
    reason="needs a per-site reader, not built in this pull request: state parks and kiosks named with no coordinate",
)
