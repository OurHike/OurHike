"""National Park Service: closures, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Corrected by skeptic: the national Alerts API has no geometry, since a closure there names a park
(`parkCode`), not a segment. The park layers above do have geometry, for the parks that publish
them, so YOSE, SEKI and GRCA closures can be drawn on the trail. The cost is a per-park list. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://developer.nps.gov/api/v1/alerts` (JSON, key): 617 alerts nationwide. Of the first 500: "
        "Information 232, Park Closure 146, Caution 107, Danger 15. `lastIndexedDate` up to 2026-09-30. Trail "
        'examples: zion "Watchman Trail closed"; crla "Cleetwood Cove Trail is CLOSED for Rehabilitation"; acad'
        ' "Southern Section of Ocean Path Closed for Repairs"; grca "INNER CANYON TRAIL CLOSURES" (Danger); '
        'mora "WILDFIRE CLOSURES: Sunrise & northern trails"; appa "List of trail closures post-Hurricane '
        "Helene\". Also in loaded data: `TRLSTATUS='Temporarily Closed'` on 60 `nps_trails` features.",
        "Skeptic adds …",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
