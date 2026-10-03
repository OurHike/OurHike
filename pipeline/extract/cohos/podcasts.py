"""The Cohos Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c4_regional_1).

Skeptic re-checked 2026-10-01: WP search for podcast/audio/radio/episode/listen returns nothing
relevant; categories are `news` (73) and `cohos-tales` (7); the 141-URL `wp-sitemap.xml` has no
audio page. Web search finds only third-party shows (e.g. "Trail Tales" #32). Stands.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("Checked the nav and WP routes.",),
    where=("https://cohostrail.org/",),
)
