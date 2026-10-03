"""Washington Trails Association: closures, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Page. WTA relays agency closures, so the authoritative channel is the agency (NPS/USFS). Restricted
by the ToS.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Weekly "Hiker Headlines" posts. For example, '
        "`/news/signpost/hiker-headlines-fall-colors-summerland-trailhead-closure-three-queens-fire-closure-reduced-9-24-26`"
        ' (2026-09-24): "Summerland trailhead will be closed Sept. 28–Oct. 31", Hoh River Bridge full-day '
        "closures, and the Three Queens Fire closure order reduced.",
    ),
    where=("https://wta.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
