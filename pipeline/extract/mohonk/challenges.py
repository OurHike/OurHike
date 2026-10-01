"""Mohonk Preserve: challenges, nothing published (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

An event, not a list of places a hiker opts into, which is the shape of #1780 — Let a club publish a
challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List. Skeptic, more searches 2026-10-01: WP `/search` for "patch", "badge" …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'WP `/search` for "challenge" and "passport" finds no opt-in programme. "Rock The Ridge" '
        '(`/rock-the-ridge/`, `modified` 2026-08-14) calls itself "A 50-mile Challenge", but it is a one-day '
        "registered race and hike (May 1, 2027).",
    ),
    where=("https://mohonkpreserve.org/",),
)
