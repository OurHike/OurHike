"""US Army Corps of Engineers: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c9_federal_state_rest).

No national list. Each district publishes in its own way, and the `.usace.army.mil` district sites
block curl. A loader would be per district and per page, which is weak.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Per district and per lake, as pages and PDFs. Measured 2026-10-01: Fort Worth District, "
        "`https://www.swf-wc.usace.army.mil/canyon/Recreation/Trails/` (HTTP 200, page: Old Hancock Trail, 4 mi"
        " one way; Guadalupe Trail, under 1 mi). Lake Georgetown's Goodwater Loop map, "
        "`https://www.swf-wc.usace.army.mil/georgetown/information/Hiking%20Trail%20Map.pdf` (HTTP 200, "
        "`application/pdf`, 446,682 bytes, a 28-mile loop with mile markers). Rock Island District's "
        "`mvr.usace.army.mil/Missions/Recreation/Coralville-Lake/Recreation/Trails/` and St. Louis District's …",
    ),
    where=(
        "https://www.swf-wc.usace.army.mil/canyon/Recreation/Trails/",
        "https://www.swf-wc.usace.army.mil/georgetown/information/Hiking%20Trail%20Map.pdf",
        "https://mvr.us",
        "https://usace.army.mil/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
