"""U.S. Army Corps of Engineers: suggested hikes, published district by district and lake by lake, and not
landed (decision 54 wave 4, section K, 2026-10-04).

Each district runs its own site and each lake its own pages: Fort Worth District's Canyon Lake trails page (two
trails, Old Hancock Trail and Guadalupe Trail, their miles in a sentence), Lake Georgetown's Goodwater Loop map
PDF, Rock Island and St. Louis districts' pages in their own layouts (the coverage audit). A reader for each is a
per-site reader for dozens of sites, not built here.

The note this replaces read, whole:

US Army Corps of Engineers: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c9_federal_state_rest).

No national list. Each district publishes in its own way, and the `.usace.army.mil` district sites block
curl. A loader would be per district and per page, which is weak.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Per district and per lake, as pages and PDFs. Measured 2026-10-01:
Fort Worth District, `https://www.swf-wc.usace.army.mil/canyon/Recreation/Trails/` (HTTP 200, page: Old
Hancock Trail, 4 mi one way; Guadalupe Trail, under 1 mi). Lake Georgetown's Goodwater Loop map,
`https://www.swf-wc.usace.army.mil/georgetown/information/Hiking%20Trail%20Map.pdf` (HTTP 200,
`application/pdf`, 446,682 bytes, a 28-mile loop with mile markers). Rock Island District's
`mvr.usace.army.mil/Missions/Recreation/Coralville-Lake/Recreation/Trails/` and St. Louis District's …

Its `where`: https://www.swf-wc.usace.army.mil/canyon/Recreation/Trails/
https://www.swf-wc.usace.army.mil/georgetown/information/Hiking%20Trail%20Map.pdf https://mvr.us
https://usace.army.mil/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.swf-wc.usace.army.mil/canyon/Recreation/Trails/ (HTTP 200, 65,274 bytes, 2026-10-04T17:39:32Z): headings 'Old Hancock Trail' and 'Guadalupe Trail', their lengths in prose",
        "(the coverage audit, 2026-10-01) Lake Georgetown's Hiking Trail Map.pdf (446,682 bytes); Rock Island and St. Louis districts' trails pages",
    ),
    where=(
        "https://www.swf-wc.usace.army.mil/canyon/Recreation/Trails/",
        "https://usace.army.mil/",
    ),
    reason="needs a per-site reader, not built in this pull request: one per district and lake, each laid out its own way",
)
