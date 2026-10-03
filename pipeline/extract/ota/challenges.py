"""Ozark Trail Association: challenges, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Outside the challenge shape in #1780 — Let a club publish a challenge — places on its own trails
that hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "No completion or patch programme. Skeptic re-check, by WP search:",
        '"thru-hik": `/thru-hiking/` (modified 2024-01-12) defines a thru-hike as "the contiguous 230-mile '
        'backbone" and points to the OTSHAB Facebook page. No recognition.',
        '"patch": store products ("OTA Patch", "Volunteer Patch") and events.',
        '"complet": map sets and events.; Verdict stands. (M) The "OT Hike and Float Challenge" is an annual '
        "fundraising weekend ($800 per participant, 20 slots), not a place-based programme.",
    ),
    where=("https://ozarktrail.com/",),
)
