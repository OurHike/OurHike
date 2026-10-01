"""NC High Peaks Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Page. 14 months stale, and an inverse list (open, not closed). Low value as a closure source.
Skeptic: re-read, still "Update 7/30/2025". One more closure line sits on `/webcams`: "The Park is
open for vehicular access from the south via the Blue Ridge Parkway from Asheville. Access from the
north …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://nchighpeaks.org/2024Hikes`, "Hiking Trails Currently Open in Our Area": a post-Helene list of'
        ' open trails with length, elevation change and difficulty. "Update 7/30/2025".',
    ),
    where=("https://nchighpeaks.org/2024Hikes",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
