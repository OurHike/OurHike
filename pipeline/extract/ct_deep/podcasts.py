"""Connecticut DEEP: podcasts, nothing published (coverage audit 2026-10-01, batch b5_nyc_nj_ct_ma_pa).

DEEP's own site was not searched for audio. Skeptic, 2026-10-01: kept, with more checks. iTunes
search for "Connecticut State Parks", "Connecticut Wildlife" and "Connecticut Geological Survey"
found no show by DEEP. `ctparks.com/sitemap.xml` (282 URLs) has no podcast or audio page. Measured.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'iTunes search for "Connecticut DEEP", "CT DEEP" and "Connecticut Energy Environmental Protection" '
        "found no show by DEEP.",
    ),
    where=("https://ctparks.com/sitemap.xml",),
)
