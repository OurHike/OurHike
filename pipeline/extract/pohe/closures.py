"""Potomac Heritage Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch c10_nst_rest).

Closures here belong to the section managers (C&O Canal NHP, NOVA Parks, Fairfax County). Nobody
publishes them as one list. The channel is NPS's: `developer.nps.gov/api/v1/alerts?parkCode=pohe`,
re-measured today at 0, while the same call returns 1 for `natr` and 16 for `iatr`. It belongs in
the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The association: no closures section (sitemap, 6 news posts; news RSS `?format=rss` exists).",
        'Skeptic: the RSS holds 7 items, 2022-07-05 to 2025-07-13. None is a closure; the nearest is "NoVa '
        'Parks Re-Mows at Trump National", 2022. NPS `pohe/planyourvisit/conditions.htm` says: "Please check '
        'directly with the local trail manager… for the most accurate and up-to-date information." NPS alerts '
        "API for `pohe`: 0 today.",
    ),
    where=("https://developer.nps.gov/api/v1/alerts?parkCode=pohe",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
