"""New Mexico Volunteers for the Outdoors: warnings, published, and not landed (coverage audit
2026-10-01, batch c6_regional_3).

The data is real, but it resets each year. Each row needs its scouted date carried through to the
card.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'CalTopo map JSON (92 features). 29 dated scouting reports, e.g. "Skyline Trail Segment FT251 | Scouted'
        ' 5/20/26 … 35 blowdowns observed … pack stock would likely have difficulty", and "10K Trail North '
        'FT200 | Scouted 4/14/26 … 19 blowdowns". `/projects-map/` (modified 2026-02-12) says the map holds '
        '"completed projects and scouting reports for the current year".',
    ),
    where=("https://nmvfo.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
