"""Trailkeepers of Oregon: places, its camping page in prose with no place listed, not landed (decision 54,
wave 5, read live 2026-10-04).

`/overnight/` is the Oregon Coast Trail's camping rules in prose: where dispersed and beach camping are allowed
and where not, and that hiker-biker sites are at state park campgrounds ("$7 to $10 per person"). It names
places in sentences and lists no site with a coordinate, so nothing lands. The state parks are Oregon Parks'
own places, and `OCT_Section_Points` (11 section ends) is an ArcGIS layer, the lead's to route.

A HIKER'S SAFETY, in the page's words, which lands nowhere: beach camping is "Not adjacent to any state park (by
any name)", not inside several towns' city limits, and "Not in western snowy plover protected zones ... from
March 15 to Sept. 15". A campsite drawn from a page like this would be the kind of confident wrong answer the
project refuses.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (`User-agent: *` disallows /wp-admin/ only), then /overnight/, read 2026-10-04 under "
        "lib/user_agent.py's agent: 200, 77,649 bytes, 47 lines of text, no coordinate, map or list of sites.",
        "the coverage audit (2026-10-01, batch c6_regional_3): `OCT_Section_Points` (11 named section ends, e.g. "
        "Fort Stevens State Park, Oswald West State Park); `/ferries-buses/` and `/parking-permits/` not opened.",
    ),
    where=("https://trailkeepersoforegon.org/overnight/", "https://trailkeepersoforegon.org/"),
    reason="published in prose: camping rules with no place listed or placed",
)
