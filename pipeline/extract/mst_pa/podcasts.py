"""Mid State Trail Association (PA): podcasts, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic re-checked 2026-10-01: the homepage's 37 distinct `/index.php/` links (latest-news,
archived-news, newsletter, downloads, web links) have no audio page; a web search found none. Joomla
has no sitemap (`/sitemap.xml` 404s through the CMS). Stands.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked the nav.",),
    where=(
        "https://mapservices.pasda.psu.edu/server/rest/services",
        "https://services6.arcgis.com/DtSEkvbAjAfDY35J/arcgis/rest/services",
        "https://hike-mst.org/",
    ),
)
