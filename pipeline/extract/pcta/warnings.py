"""Pacific Crest Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

The Interactive Map's fire, smoke and IFPL layers are third-party (NIFC, ODF, WA DNR, NWS), so they
go to `_shared/`, not here.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://closures.pcta.org/ (html_page);
https://www.pcta.org/discover-the-trail/trail-conditions/ (html_page).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The wildfire rows above (`Type = Wildfire`, `Miles_of_PCT_Burned`) are burn-area hazard points. "
        "`pcta.org/discover-the-trail/trail-conditions/` was found by web search and returns 403 from here.",
    ),
    where=(
        "https://pcta.org/discover-the-trail/trail-conditions/",
        "https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
