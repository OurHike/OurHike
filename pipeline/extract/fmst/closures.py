"""Friends of the Mountains-to-Sea Trail: closures, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Closures with geometry, in KML. Google-hosted, so the captcha does not apply.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Helene KML (above). Each line carries "Trail Status": 2 `CLOSED` (Segment 4, "West of N Fork Catawba '
        'crossing…" 0.1 mi and "Blue Ridge Parkway Boundary to NC 80" 2.6 mi), 1 detour (South Toe River, 7.7 '
        "mi) and 9 open. Plus detour pages found by search: `/possum-track-detour/`, `/south-toe-detour/`, "
        '`/i-540-detour/` (I-540 construction, "through February 2028"), `/steels-creek-detour/`, '
        "`/harper-creek-detour/`, `/eno-river-state-park-detour/`. Plus `/the-trail/trail-updates/`.",
    ),
    where=("https://mountainstoseatrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
