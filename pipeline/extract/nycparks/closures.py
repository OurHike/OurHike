"""NYC Parks: closures, refused by www.nycgovparks.org's robots.txt (decision 53, phase B, 2026-10-03).

NYC Parks' one machine-readable closure channel is its `bigapps` closure file, and the host's
robots.txt disallows it for every agent, ours included: `Disallow: /*json` catches the JSON file and
`Disallow: /*xml` its XML twin. The coverage audit read the file on 2026-10-01 without reading
robots.txt; the decision 53 inventory found the rule and did not fetch. NYC Open Data lists the same
file as dataset `efsz-uj8v` "Park Closure Notifications", but only as a pointer whose accessPoints
are those two nycgovparks.org URLs, so there is no second copy to read. The route forward is NYC
Parks' permission, which the maintainer asks for.

The coverage audit's note (2026-10-01): mostly facility closures (recreation centres, marinas,
playgrounds, the Tide Gate Bridge in Flushing Meadows), so the trail yield is low.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "www.nycgovparks.org/robots.txt, read 2026-10-03 under lib/user_agent.py's agent: the `User-agent: *` "
        "group holds `Disallow: /*json` and `Disallow: /*xml`, which match /bigapps/DPR_ParkClosure_001.json and "
        "its .xml twin; neither was requested.",
        "(the inventory, 2026-10-03) `https://data.cityofnewyork.us/api/views/efsz-uj8v.json`: 'Park Closure "
        "Notifications', an href-type entry whose accessPoints are the nycgovparks.org JSON and XML files, "
        "'Update Frequency: As needed'.",
        "(coverage audit, 2026-10-01) `/bigapps/DPR_ParkClosure_001.json`: 8,069 rows (3,352 not archived), "
        "Last-Modified 2026-09-30 08:00 GMT, so regenerated daily. Fields `start`, `end`, `closure_type`, "
        "`message`, `Prop_ID` (the `gispropnum` key nyc_park_polygons uses), `created`, `modified`, "
        "`is_archived`. 30 rows active on 2026-10-01: Closed 14, Partially Closed 2, Open 14. Only 2 rows ever "
        'mention a trail; the newest, "The Pat Dolan Trail will be closed due to construction from August 3-7, '
        '2026."',
    ),
    where=(
        "https://www.nycgovparks.org/robots.txt",
        "https://www.nycgovparks.org/bigapps/DPR_ParkClosure_001.json",
        "https://data.cityofnewyork.us/api/views/efsz-uj8v.json",
    ),
    terms="www.nycgovparks.org/robots.txt (read 2026-10-03), group `User-agent: *`: `Disallow: /*json` / `Disallow: /*xml`",
    reason="refused: robots.txt disallows the closure file for every agent; held until NYC Parks permits",
)
