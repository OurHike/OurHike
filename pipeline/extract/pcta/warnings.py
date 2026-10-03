"""Pacific Crest Trail Association: warnings, walled: both of PCTA's own notice pages answer our agent with a
challenge (decision 53's inventory, 2026-10-03).

https://closures.pcta.org/ answered HTTP 429 with Vercel's Security Checkpoint (`x-vercel-mitigated:
challenge`, title 'Vercel Security Checkpoint'), and its robots.txt answered the same challenge;
https://www.pcta.org/discover-the-trail/trail-conditions/ answered HTTP 403 with Cloudflare's challenge
(`cf-mitigated: challenge`, title 'Just a moment...'), though www.pcta.org's robots.txt allows the path.
Neither was solved, retried or approached with another agent (decision 39). Held until PCTA answers.

What PCTA does publish openly is its two ArcGIS layers, extracted in pcta/closures.py; their wildfire
rows (`Type = Wildfire`, `Miles_of_PCT_Burned`) are burn-area hazard points, the warnings half of
that table. The Interactive Map's fire, smoke and IFPL layers are third-party (NIFC, ODF, WA DNR, NWS),
so they belong to `_shared/`, not here.

Before this, the file was the coverage audit's note (confirmed 2026-10-01, batch b7_long_trails_states),
whose `checked` is kept below.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(decision 53 inventory, batch 2, 2026-10-03) https://closures.pcta.org/: HTTP 429, header "
        "x-vercel-mitigated: challenge, page title 'Vercel Security Checkpoint'; /robots.txt answered the same. "
        "Not bypassed, not retried.",
        "(decision 53 inventory, batch 2, 2026-10-03) https://www.pcta.org/discover-the-trail/trail-conditions/: "
        "HTTP 403, header cf-mitigated: challenge, page title 'Just a moment...'; www.pcta.org's robots.txt "
        "('User-agent: *') disallows only /wp-content/uploads/wp-import-export-lite/. Not bypassed, not retried.",
        "(coverage audit, 2026-10-01) The wildfire rows above (`Type = Wildfire`, `Miles_of_PCT_Burned`) are "
        "burn-area hazard points. `pcta.org/discover-the-trail/trail-conditions/` was found by web search and "
        "returns 403 from here.",
    ),
    where=(
        "https://closures.pcta.org/",
        "https://www.pcta.org/discover-the-trail/trail-conditions/",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services",
    ),
    reason=(
        "a wall: both notice pages answer our agent with a challenge (Vercel 429, Cloudflare 403); held until PCTA "
        "answers, and its open ArcGIS layers land in pcta/closures.py"
    ),
)
