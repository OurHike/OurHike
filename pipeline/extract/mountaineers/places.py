"""The Mountaineers: places, behind a wall (decision 54, wave 5, read 2026-10-04). The Routes & Places trailhead
records answered Cloudflare's challenge ('Just a moment...', 403) to our named agent, as the coverage audit
found it could not read the site (2026-10-01). A wall is UNKNOWN and stops there: not solved, not worked
round.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "www.mountaineers.org/robots.txt (Plone's; /@@search and the faceted query disallowed) allows the path; "
        "/activities/routes-places/cougar-mountain-harvey-manning-trailhead answered 403 with the title 'Just a "
        "moment...', read 2026-10-04 under lib/user_agent.py's agent.",
        "the coverage audit (2026-10-01, batch c5_regional_2): count and format were not measured; the batch called"
        " the site unreadable.",
    ),
    where=("https://www.mountaineers.org/activities/routes-places/cougar-mountain-harvey-manning-trailhead",),
    reason="walled: Cloudflare's challenge answers our named agent; not solved, not worked round",
)
