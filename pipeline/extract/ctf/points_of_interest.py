"""Colorado Trail Foundation: points of interest, held for permission: the 881 surveyed waypoints sit on
the CTF's surveyor's site, whose terms forbid copying or use without written permission (decision 54,
wave 2, read 2026-10-04).

Bear Creek Survey, the CTF's pro-bono surveyor and Map Book cartographer, publishes
`Data/CT_2020_GPX.zip`: one GPX, 881 waypoints with letter codes (`01-033WT` …) whose descriptions are
water and navigation notes ('Stream (Flowing 2018)', 'Small Stream (Dry 2018)', 'Trail Junction',
'Spring'). The file is not the CTF's own and its host's terms are a permission gate, so it is a dated
note quoting them (the dlt skill: 'Note now, load on permission'), and the maintainer asks Bear Creek or
the CTF. It was read once to see what it holds, and nothing of it is kept.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        'http://bearcreeksurvey.com/Data/CT_2020_GPX.zip, read 2026-10-04 under lib/user_agent.py\'s agent (robots.txt 404, no rule): 20,583 bytes, ETag "5067-59df0c9587913", Last-Modified 2020-02-06; one member, CT_2020_WP_fin.gpx (238,064 bytes), 881 waypoints, unique on the geometry with `desc` (871 distinct points).',
        "http://bearcreeksurvey.com/, read 2026-10-04: the footer quoted in `terms`.",
        "(coverage audit, 2026-10-01) the letter coding is explained in `Data/Mapbook_Prefaces.pdf`; the CTF's own site publishes no point layer.",
    ),
    where=(
        "https://bearcreeksurvey.com/Data/CT_2020_GPX.zip",
        "https://bearcreeksurvey.com/",
        "https://coloradotrail.org/",
    ),
    terms="All material on this website is the property of Bear Creek Survey Service and may not be copied or used in any manner without express written permission. (http://bearcreeksurvey.com/, footer, read 2026-10-04)",
    reason="held for permission: the host's terms forbid copying or using its material without express written permission",
)
