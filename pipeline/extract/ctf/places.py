"""Colorado Trail Foundation: places, behind a wall (decision 54, wave 5, read 2026-10-04). The segments page
(segment trailheads and nearby towns, the coverage audit's search snippet, 2026-10-01) answered SiteDistrict's
'Access Denied' to our named agent, the wall decision 53's inventory met on the same host. A wall is UNKNOWN
and stops there: not retried, not worked round.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "coloradotrail.org/robots.txt answered 403 and /trail/segments-of-the-ct/ answered 403 'Access Denied' "
        "(server sitedistrict-nginx), read 2026-10-04 under lib/user_agent.py's agent.",
        "the coverage audit (2026-10-01, batch c7_regional_4): segment trailheads and nearby towns (search snippet).",
    ),
    where=("https://coloradotrail.org/trail/segments-of-the-ct/",),
    reason="walled: the host answers our named agent 403 'Access Denied'; not retried, not worked round",
)
