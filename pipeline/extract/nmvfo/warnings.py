"""New Mexico Volunteers for the Outdoors: warnings, refused by CalTopo's robots.txt (decision 53, phase B,
2026-10-03).

NMVFO's scouting reports live on a CalTopo map whose data comes only from CalTopo's `/api/`, which
caltopo.com's robots.txt disallows for every agent, ours included, so it is not fetched. The viewer
page (`caltopo.com/m/HHBSV6V`) is allowed but is a JavaScript client that reads the same `/api/`,
and nmvfo.org's projects map page embeds it. The route forward is permission (NMVFO's, with a
CalTopo export) that the maintainer asks for, or the reports published elsewhere.

The coverage audit's note (2026-10-01): the data is real but resets each year, and each row needs its
scouted date carried through to the card.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "caltopo.com/robots.txt, read 2026-10-03 under lib/user_agent.py's agent: `User-agent: *` then "
        "`Disallow: /api/` among ten Disallow lines; `/api/v1/map/HHBSV6V/since/0` falls under it, so it was not "
        "requested (the decision 53 inventory, batch 3, read the same rule).",
        '(coverage audit, 2026-10-01) CalTopo map JSON (92 features). 29 dated scouting reports, e.g. "Skyline '
        "Trail Segment FT251 | Scouted 5/20/26 … 35 blowdowns observed … pack stock would likely have "
        'difficulty", and "10K Trail North FT200 | Scouted 4/14/26 … 19 blowdowns". `/projects-map/` (modified '
        '2026-02-12) says the map holds "completed projects and scouting reports for the current year".',
    ),
    where=(
        "https://caltopo.com/robots.txt",
        "https://nmvfo.org/projects-map/",
        "https://nmvfo.org/",
    ),
    terms="caltopo.com/robots.txt (read 2026-10-03): `User-agent: *` / `Disallow: /api/`",
    reason="refused: robots.txt disallows the only machine-readable path for every agent; held until NMVFO or CalTopo permits",
)
