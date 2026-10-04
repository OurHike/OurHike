"""Keystone Trails Association: points of interest, refused by CalTopo's robots.txt (decision 55 lists
CalTopo among the refusals).

KTA publishes its own GPS data only as CalTopo maps, whose data comes from caltopo.com's `/api/`, which
caltopo.com's robots.txt disallows for every agent, ours included (read again 2026-10-04). So it is not
fetched, and the route forward is permission, KTA's or CalTopo's for an export, which the maintainer
asks for, as kta/closures.py records for the maps' one closure marker.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "caltopo.com/robots.txt, read 2026-10-04 under lib/user_agent.py's agent: `User-agent: *` and ten Disallow lines, `Disallow: /api/` among them; a map's data URL, `/api/v1/map/<id>/since/0`, falls under it, so none was requested.",
        "the same 6 CalTopo maps' 52 markers (Quehanna 12, Allegheny Front 10, Thunder Swamp 5, Pinchot 5, Conestoga 0, Laurel Highlands 20), almost all trailhead parking, plus shelter-area junctions and two named features (the coverage audit's skeptic, 2026-10-01). ATC's loaded layers already carry KTA's A.T. shelter, parking and viewpoints (code 11).",
    ),
    where=(
        "https://caltopo.com/robots.txt",
        "https://www.kta-hike.org/maps.html",
        "https://kta-hike.org/",
    ),
    terms="caltopo.com/robots.txt (read 2026-10-04): `User-agent: *` / `Disallow: /api/`",
    reason="refused: robots.txt disallows the only machine-readable path for every agent; held until KTA or CalTopo permits",
)
