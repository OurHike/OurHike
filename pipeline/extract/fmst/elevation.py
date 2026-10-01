"""Friends of the Mountains-to-Sea Trail: elevation, nothing published (coverage audit 2026-10-01,
batch c7_regional_4).

USGS 3DEP. The segment guide PDFs were not readable.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Nav menu read (via WebFetch). Sitemap and wp-json are blocked by the captcha.",),
    where=("https://mountainstoseatrail.org/",),
)
