"""Friends of the Blue Hills: podcasts, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic re-checked 2026-10-01: "audio" and "episode" searches return only posts. The `facebook-live`
category (36 posts, "Blue Hills A-Live") is video. A web search found FBH's director as a guest on
"Guides Gone Wild" (Buzzsprout), which is somebody else's show. Stands.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("WP search returned 0.",),
    where=(
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services",
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services",
        "https://friendsofthebluehills.org/",
    ),
)
