"""Mid State Trail Association (PA): challenges, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/the-trail/end-to-end-list` (certified end-to-enders since 2012), "
        "`/resources/end-2-end-certification`, `/resources/mega-meter`, `/the-organization/patches`.",
    ),
    where=("https://hike-mst.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
