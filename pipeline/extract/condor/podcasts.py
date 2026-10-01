"""Condor Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Skeptic: the "Condor Trail Talk" series (2016–2018) in LPFA's posts were in-person talks, not audio.
Verdict stands. (M)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('WP search for "podcast" returned 0.',),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services",
        "https://condortrail.com/",
    ),
)
