"""Lone Star Hiking Trail Club: places, refused: lonestartrail.org answers our named agent 403 (decision 54, wave
5, read 2026-10-04). The 14-trailhead table (directions and Google Maps links) and the guide's support list
are on the club's site, which refuses lib/user_agent.py's agent, as ELT.md's decision 39 records for its
ClubExpress files: a host that refuses our own named agent has refused us, and no other agent is tried. Held
until the club answers.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "lonestartrail.org/robots.txt answered 403, then https://lonestartrail.org/ answered 403 Forbidden "
        "(awselb/2.0, 118 bytes), read 2026-10-04 under lib/user_agent.py's agent.",
        "the coverage audit (2026-10-01, batch c8_regional_5): the 14-trailhead table with Google links; the "
        "guide's off-trail support list; the SHNF compartment numbers per section.",
    ),
    where=(
        "https://lonestartrail.org/",
        "https://apps.fs.usda.gov/arcx/rest/services",
    ),
    reason="refused: the club's host answers our named agent 403; no other agent is tried (decision 39)",
)
