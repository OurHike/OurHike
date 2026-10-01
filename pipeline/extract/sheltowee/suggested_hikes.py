"""Sheltowee Trace Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/organizedhikes` (members only, e.g. "Van Hook Falls", 2026-10-11, "5.7 miles … 626ft of gain"). The '
        "Hiker Challenge schedule PDF, `/s/2026NorthtoSouthHikerChallengeSchedule_updated_Sept30_2026.pdf`.",
    ),
    where=("https://sheltoweetrace.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
