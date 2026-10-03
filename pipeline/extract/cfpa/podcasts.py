"""Connecticut Forest & Park Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Only a guest spot on WNPR "Where We Live", 2026-07-09.',
        "Skeptic: none of the 10 WordPress categories is a podcast category. `rock-root-trail` (6) is a donor "
        "and volunteer profile series. WP REST `search=podcast` returns 1 unrelated post (Advancing "
        'Conservation One Image at a Time). iTunes "Connecticut Forest Park" and "ctwoodlands" find no CFPA '
        "show.",
    ),
    where=("https://ctwoodlands.org/",),
)
