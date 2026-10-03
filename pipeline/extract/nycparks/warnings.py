"""NYC Parks: warnings, refused with the closures file they come from (decision 53, phase B, 2026-10-03).

The warnings-shaped rows are the closure file's `closure_type = 'Open'` notices, and that file is
disallowed by www.nycgovparks.org's robots.txt for every agent (nycparks/closures.py quotes the
rule), so they fall with it. Under decision 7 they would land in `warnings`, labelled "not
reviewed". Trail hours (dusk closing) are the one hazard-shaped fact the coverage audit found here:
a hiker in a park after hours.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "www.nycgovparks.org/robots.txt, read 2026-10-03: `User-agent: *` / `Disallow: /*json` covers "
        "/bigapps/DPR_ParkClosure_001.json, the file these rows are in; not requested.",
        "(coverage audit, 2026-10-01) The same feed's `closure_type = 'Open'` rows are notices that close "
        "nothing: 578 all-time, 14 active, for example the Ecology Park habitat notice at `B406`. `Parks Signs` "
        'carries trail hours ("Trail With Hours"). Checked and rejected: Urban Park Ranger Animal Condition '
        "Response (see Do not load); `Parks Inspection Program – Conditions & Hazards` `ibip-ftv5`, which is "
        "inspection findings, not public notices; `DPR_BeachesClosures_001`, which is water quality and is kept "
        "out of `warnings` by decision 2.",
    ),
    where=(
        "https://www.nycgovparks.org/robots.txt",
        "https://data.cityofnewyork.us/d/ibip-ftv5",
    ),
    terms="www.nycgovparks.org/robots.txt (read 2026-10-03), group `User-agent: *`: `Disallow: /*json` / `Disallow: /*xml`",
    reason="refused: robots.txt disallows the closure file these notices are in, for every agent; held until NYC Parks permits",
)
