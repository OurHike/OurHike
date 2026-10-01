"""Green Mountain Club: places, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

A.T. towns in VT are already LOADED via `communities`. Long Trail towns are not.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Visitor centres: `/about/visitor-centers/gmc-visitor-center/`, `…/barnes-camp/`, "
        "`…/mansfield-visitor-center/`. `PARKING_MASTER` (96 named trailheads) works as a trailhead directory. "
        "The End-to-Ender's Guide (trail towns and amenities) at `/get-the-2026-end-to-enders-guide/` is behind"
        " an email form.",
    ),
    where=("https://greenmountainclub.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
