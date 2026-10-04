"""Roanoke Appalachian Trail Club: places, not read: ratc.org's robots.txt answered 502 (decision 54, wave 5,
2026-10-04), which RFC 9309 reads as a full disallow, so the club's trailhead directory with its overnight-
parking rules (Trout Creek 'Overnight parking allowed', Dragon's Tooth 'Overnight parking is NOT allowed',
McAfee Knob 'DO NOT PARK ALONG 311 ... ticketed and towed', the coverage audit 2026-10-01) was not requested.
Its fixes are Google Maps links, Google's places rather than the club's, so a reader would need the club's own
fixes in any case. ATC's `parking` (22) and `communities` are loaded.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "ratc.org/robots.txt answered 502 at 2026-10-04T17:17:30Z under lib/user_agent.py's agent: unreachable, a "
        "full disallow by RFC 9309 §2.3.1.4, so no page was requested.",
        "the coverage audit (2026-10-01, batch c3_at_clubs_south): the Triple Crown page, a trailhead directory "
        "with overnight rules; Google Maps coordinates in the links.",
    ),
    where=(
        "https://ratc.org/robots.txt",
        "https://ratc.org/",
    ),
    reason="not read: robots.txt answered 502, a full disallow (RFC 9309); and the page's fixes are Google's links",
)
