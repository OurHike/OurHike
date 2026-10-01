"""Save Mount Diablo: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

Terms-blocked.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/experience/field-guides/hikes-in-the-diablo-range/` lists 47 numbered hikes by region, each linking "
        'a blog post, e.g. `/blog/mount-diablo-state-park-five-peaks-hike/`. The "Northern Diablo Range Hiking '
        'Guide" PDF is behind an email form.',
    ),
    where=("https://savemountdiablo.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
